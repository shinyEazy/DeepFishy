import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urlparse

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from deepfishy.shared.tracing import wrap_with_current_tracing_context
from engine.tools.critique_chart import critique_chart
from engine.tools.execute_chart_code import execute_chart_code
from engine.tools.get_content_by_source_urls import get_content_by_source_urls
from engine.tools.get_current_date import get_current_date
from engine.tools.query_knowledge_graph import (
    query_graph_natural,
    query_knowledge_graph,
)
from engine.tools.search_and_build_graph import set_current_session_id


class SectionTask(TypedDict, total=False):
    index: int
    title: str
    heading: str
    outline_chunk: str
    dir_name: str
    writer_mode: str
    build_artifact: Dict[str, Any]


class SectionResult(TypedDict, total=False):
    index: int
    title: str
    dir_name: str
    evidence_path: str
    bull_case_path: str
    bear_case_path: str
    draft_path: str
    critique_path: str
    evidence_pack: str
    draft: str
    critique: Dict[str, Any]


class WriteState(TypedDict, total=False):
    messages: list
    outline: str
    sections: List[SectionTask]
    section_results: List[SectionResult]
    critique_round: int
    pass_threshold: bool
    sections_needing_revision: List[Dict[str, Any]]


class LangGraphWriteAgent:
    def __init__(self, graph, workspace_path: Optional[str], session_id: Optional[str]):
        self._graph = graph
        self._workspace_path = workspace_path
        self._session_id = session_id
        self._expects_task_delegation = False

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._graph.invoke({"messages": payload.get("messages", [])})


def _extract_frontmatter_body(markdown_text: str) -> str:
    match = re.match(r"---(.*?)---(.*)", markdown_text, re.DOTALL)
    if match:
        return match.group(2).strip()
    return markdown_text.strip()


class WriterOrchestrator:
    MAX_CRITIQUE_ROUNDS = 2
    MAX_CHARTS_PER_SECTION = 2
    MAX_CHART_REVISIONS = 3
    MAX_EVIDENCE_QUERIES = 4
    MAX_SECTION_EVIDENCE_RECORDS = 24
    MAX_MODEL_EVIDENCE_RECORDS = 80

    def __init__(
        self,
        model: BaseChatModel,
        session_id: Optional[str] = None,
        output_base_path: str = "outputs",
    ):
        self.model = model
        self.session_id = session_id
        self.output_base_path = output_base_path
        self._agent = None
        self._workspace_path = None
        self._bull_prompt = self._load_prompt("bull_agent.md")
        self._bear_prompt = self._load_prompt("bear_agent.md")
        self._critique_prompt = self._load_prompt("critique_agent.md")
        self._chart_prompt = self._load_prompt("chart_generator.md")
        self._synth_prompt = self._load_synth_prompt()
        self._build_artifact_cache: Optional[Dict[str, Any]] = None
        self._report_model_snapshot: Optional[str] = None

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).resolve().parents[1] / "subagents" / filename
        return _extract_frontmatter_body(prompt_path.read_text(encoding="utf-8"))

    def _load_synth_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parents[1]
            / "prompts"
            / "synthesizer_orchestrator_prompt.py"
        )
        raw_text = prompt_path.read_text(encoding="utf-8")
        match = re.search(r'"""(.*)"""', raw_text, re.DOTALL)
        return match.group(1).strip() if match else raw_text.strip()

    def _extract_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    parts.append(str(block["text"]))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return str(content)

    def _get_workspace_path(self) -> Optional[str]:
        if not self.session_id:
            return None
        if self._workspace_path is None:
            self._workspace_path = os.path.join(self.output_base_path, self.session_id)
            os.makedirs(self._workspace_path, exist_ok=True)
            os.makedirs(os.path.join(self._workspace_path, "images"), exist_ok=True)
        return self._workspace_path

    def _write_file(self, relative_path: str, content: str) -> str:
        workspace_path = self._get_workspace_path()
        if not workspace_path:
            raise RuntimeError("Writer workspace path is required.")
        path = Path(workspace_path) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _read_outline(self) -> str:
        workspace_path = self._get_workspace_path()
        if not workspace_path:
            raise RuntimeError("Write phase requires a workspace with outline.md.")
        outline_path = Path(workspace_path) / "outline.md"
        if not outline_path.exists():
            raise FileNotFoundError(f"Outline file not found: {outline_path}")
        return outline_path.read_text(encoding="utf-8").strip()

    def _normalize_section_key(self, value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    def _load_build_artifact_cache(self) -> Dict[str, Any]:
        if self._build_artifact_cache is not None:
            return self._build_artifact_cache

        workspace_path = self._get_workspace_path()
        artifact_path = (
            Path(workspace_path) / "section_evidence_map.json"
            if workspace_path
            else None
        )
        if artifact_path and artifact_path.exists():
            try:
                self._build_artifact_cache = json.loads(
                    artifact_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                self._build_artifact_cache = {"sections": []}
        else:
            self._build_artifact_cache = {"sections": []}
        return self._build_artifact_cache

    def _get_build_artifact_for_section(
        self, title: str, heading: str
    ) -> Dict[str, Any]:
        normalized_title = self._normalize_section_key(title)
        normalized_heading = self._normalize_section_key(heading)

        for artifact in self._load_build_artifact_cache().get("sections", []):
            if not isinstance(artifact, dict):
                continue
            artifact_title = self._normalize_section_key(
                str(artifact.get("section_title", ""))
            )
            if artifact_title and artifact_title == normalized_title:
                return artifact

            artifact_heading = self._normalize_section_key(
                str(artifact.get("heading_line", ""))
            )
            if artifact_heading and artifact_heading == normalized_heading:
                return artifact

        return {}

    def _get_source_domain(self, url: str) -> str:
        if not url:
            return ""
        try:
            return (urlparse(url).netloc or "").lower().replace("www.", "")
        except Exception:
            return ""

    def _source_quality_tier(self, url: str) -> int:
        domain = self._get_source_domain(url)
        lowered = (url or "").lower()
        if not domain:
            return 0

        rejected_domains = [
            "goonus.io",
            "chanhtuoi.com",
            "studocu.com",
            "baomoi.com",
            "duytan.edu.vn",
            "markettimes.vn",
            "thuongtruong.com.vn",
        ]
        if any(pattern in domain for pattern in rejected_domains):
            return 0

        official_domains = [
            "mbbank.com.vn",
            "sbv.gov.vn",
            "mof.gov.vn",
            "ssc.gov.vn",
            "hsx.vn",
            "hnx.vn",
            "tapchicongsan.org.vn",
        ]
        if any(pattern in domain for pattern in official_domains):
            return 4

        broker_domains = [
            "masvn.com",
            "vndirect.com.vn",
            "acbs.com.vn",
            "vcbs.com.vn",
            "kbsv.com.vn",
            "nhsv.vn",
            "dnse.com.vn",
            "aseansc.com.vn",
            "cafef1.mediacdn.vn",
            "rs.nguoiquansat.vn",
        ]
        if any(pattern in domain for pattern in broker_domains):
            return 4 if lowered.endswith(".pdf") or "bao-cao" in lowered else 3

        trusted_news_domains = [
            "vneconomy.vn",
            "cafef.vn",
            "vietstock.vn",
            "thoibaotaichinhvietnam.vn",
            "vietnamfinance.vn",
            "tinnhanhchungkhoan.vn",
            "thitruongtaichinhtiente.vn",
            "nhandan.vn",
            "vietnamnet.vn",
            "tapchikinhtetaichinh.vn",
            "kinhte.congthuong.vn",
            "nhadautu.vn",
            "vnbusiness.vn",
        ]
        if any(pattern in domain for pattern in trusted_news_domains):
            return 2

        if lowered.endswith(".pdf"):
            return 3

        return 1

    def _section_style(self, section: SectionTask) -> str:
        title = str(section.get("title", "")).lower()
        if self._is_title_section(section):
            return "title"
        if "định giá" in title or "khuyến nghị" in title or "valuation" in title:
            return "valuation"
        if "rủi ro" in title or "cảnh báo" in title or "risk" in title:
            return "risk"
        if "triển vọng" in title or "dự báo" in title or "forward" in title:
            return "outlook"
        if "tài chính" in title or "financial" in title:
            return "financial"
        if "bối cảnh" in title or "nền tảng" in title or "hồ sơ" in title:
            return "background"
        return "general"

    def _is_strict_source_section(self, section: SectionTask) -> bool:
        return self._section_style(section) in {
            "financial",
            "outlook",
            "valuation",
            "risk",
        }

    def _section_specific_guidance(self, section: SectionTask) -> str:
        style = self._section_style(section)
        if style == "title":
            return (
                "- Viết ngắn gọn, chỉ nêu luận điểm đầu tư trung tâm và 2-3 fact quan trọng nhất.\n"
                "- Không thêm Key Drivers hay Conclusion/Outlook theo mẫu cứng.\n"
            )
        if style == "background":
            return (
                "- Chỉ giữ các thông tin nền trực tiếp phục vụ luận điểm đầu tư; bỏ bớt lịch sử/phụ lục không cần thiết.\n"
                "- Không thêm Key Drivers hay Conclusion/Outlook nếu outline không yêu cầu.\n"
            )
        if style == "financial":
            return (
                "- Phải có một bảng KPI ngắn gọn nếu evidence đủ, ưu tiên: tín dụng, huy động, CASA, NIM, NPL, CIR, ROE, PBT/PAT.\n"
                "- Tập trung vào xu hướng, động lực và chất lượng lợi nhuận; tránh kể lại số liệu rời rạc.\n"
                "- Không thêm Key Drivers hay Conclusion/Outlook theo mẫu nếu không thực sự cần.\n"
            )
        if style == "outlook":
            return (
                "- Phải tách rõ giả định, biến số chính và kịch bản cơ sở.\n"
                "- Nếu nêu dự phóng, phải nói rõ cơ sở và mức độ chắc chắn; không dùng câu dự báo chung chung.\n"
            )
        if style == "valuation":
            return (
                "- Phải có các phần rõ ràng: `### Phương pháp & Giả định`, `### Kết quả định giá`, `### Khuyến nghị`.\n"
                "- Phải nêu một mức giá mục tiêu cơ sở duy nhất kèm horizon/thời điểm; có thể thêm bull/bear range nhưng không được chỉ nêu range chung chung.\n"
                "- Phải giải thích cầu nối từ giả định chính -> chỉ số định giá -> giá mục tiêu.\n"
            )
        if style == "risk":
            return (
                "- Trình bày mỗi rủi ro theo logic: nguyên nhân -> kênh tác động -> chỉ tiêu chịu ảnh hưởng.\n"
                "- Không thêm phần Positive/Key Drivers trong section rủi ro.\n"
            )
        return (
            "- Bám sát outline gốc và chỉ thêm cấu trúc phụ khi nó làm section rõ hơn.\n"
            "- Tránh chèn các block mẫu lặp lại giữa các section.\n"
        )

    def _source_policy_block(self) -> str:
        return (
            "Source policy:\n"
            "- Ưu tiên nguồn chính thức của doanh nghiệp/cơ quan quản lý và PDF research từ CTCK.\n"
            "- Báo tài chính/chứng khoán chính thống chỉ dùng để bổ sung bối cảnh, không làm nền chính cho số liệu trọng yếu khi đã có nguồn tốt hơn.\n"
            "- Không dùng nguồn tổng hợp/giải thích phổ thông/diễn đàn/tài liệu học tập cho claim định lượng trọng yếu.\n"
            "- Chỉ liệt kê những nguồn thực sự được dùng trong section.\n"
            "- Mỗi reference phải có URL đầy đủ theo đúng format `[1] Tiêu đề: [url](url)`.\n"
        )

    def _filter_sources_by_quality(
        self, section: SectionTask, sources: List[Dict[str, Any]], limit: int = 6
    ) -> List[Dict[str, Any]]:
        decorated: List[Dict[str, Any]] = []
        seen = set()
        for source in sources or []:
            if not isinstance(source, dict):
                continue
            url = str(source.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            tier = self._source_quality_tier(url)
            if tier <= 0:
                continue
            decorated.append(
                {
                    "url": url,
                    "title": str(source.get("title") or url).strip(),
                    "quality_tier": tier,
                    "domain": self._get_source_domain(url),
                }
            )

        decorated.sort(
            key=lambda item: (
                -int(item.get("quality_tier", 0)),
                str(item.get("domain", "")),
                str(item.get("title", "")),
            )
        )

        if not decorated:
            return []

        strict = self._is_strict_source_section(section)
        high_quality = [item for item in decorated if int(item["quality_tier"]) >= 3]
        acceptable = [item for item in decorated if int(item["quality_tier"]) >= 2]

        if strict and high_quality:
            return high_quality[:limit]
        if acceptable:
            return acceptable[:limit]
        return decorated[:limit]

    def _record_quality_tier(self, record: Dict[str, Any]) -> int:
        candidate_urls: List[str] = []
        primary_url = str(record.get("primary_url", "")).strip()
        if primary_url:
            candidate_urls.append(primary_url)
        source_urls = record.get("source_urls", [])
        if isinstance(source_urls, list):
            candidate_urls.extend(
                str(url).strip() for url in source_urls if str(url).strip()
            )
        if not candidate_urls:
            return 0
        return max(self._source_quality_tier(url) for url in candidate_urls)

    def _filter_evidence_records_by_quality(
        self, section: SectionTask, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        decorated: List[Dict[str, Any]] = []
        for record in records or []:
            if not isinstance(record, dict):
                continue
            tier = self._record_quality_tier(record)
            if tier <= 0:
                continue
            enriched = dict(record)
            enriched["quality_tier"] = tier
            decorated.append(enriched)

        decorated.sort(
            key=lambda item: (
                -int(item.get("quality_tier", 0)),
                str(item.get("primary_url", "")),
                str(item.get("facts", "")),
            )
        )

        strict = self._is_strict_source_section(section)
        high_quality = [item for item in decorated if int(item["quality_tier"]) >= 3]
        acceptable = [item for item in decorated if int(item["quality_tier"]) >= 2]

        if strict and high_quality:
            return high_quality[: self.MAX_SECTION_EVIDENCE_RECORDS]
        if acceptable:
            return acceptable[: self.MAX_SECTION_EVIDENCE_RECORDS]
        return decorated[: self.MAX_SECTION_EVIDENCE_RECORDS]

    def _build_report_model_snapshot(self, sections: List[SectionTask]) -> str:
        evidence_rows: List[Dict[str, Any]] = []
        seen = set()
        for section in sections:
            artifact = section.get("build_artifact") or {}
            filtered_records = self._filter_evidence_records_by_quality(
                section, artifact.get("evidence_records", [])
            )
            for record in filtered_records:
                fact = str(record.get("facts", "")).strip()
                primary_url = str(record.get("primary_url", "")).strip()
                key = (fact, primary_url)
                if not fact or key in seen:
                    continue
                seen.add(key)
                evidence_rows.append(
                    {
                        "fact": fact,
                        "source_url": primary_url,
                        "quality_tier": int(record.get("quality_tier", 0)),
                    }
                )

        if not evidence_rows:
            return "No canonical report model could be built from the current evidence."

        prompt = (
            "Bạn đang tạo một `canonical report model` dùng chung cho toàn bộ báo cáo.\n"
            "Chỉ dùng facts được cung cấp. Không suy diễn nếu evidence không đủ.\n"
            "Nếu chủ thể là ngân hàng, ưu tiên: tổng tài sản, tín dụng, huy động, CASA, NIM, NPL, LLR, CIR, PBT/PAT, ROE, BVPS/PB, giả định tăng trưởng.\n"
            "Trả về markdown ngắn gọn theo cấu trúc:\n"
            "## Canonical Report Model\n"
            "### Core Facts\n"
            "| Chỉ tiêu | Giá trị | Kỳ | Nguồn |\n"
            "### Forecast Anchors\n"
            "| Biến số | 2024A | 2025E | 2026E | Nguồn |\n"
            "### Valuation Anchors\n"
            "| Anchor | Giá trị | Ghi chú | Nguồn |\n"
            "Dùng `N/A` nếu không đủ evidence.\n"
        )
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(
                        content=json.dumps(
                            evidence_rows[: self.MAX_MODEL_EVIDENCE_RECORDS],
                            ensure_ascii=False,
                            indent=2,
                        )
                    ),
                ]
            )
            snapshot = self._extract_text(response.content).strip()
        except Exception:
            snapshot = ""

        return (
            snapshot
            or "No canonical report model could be built from the current evidence."
        )

    def _ensure_report_model_snapshot(self, sections: List[SectionTask]) -> str:
        if self._report_model_snapshot is None:
            self._report_model_snapshot = self._build_report_model_snapshot(sections)
            self._write_file("company_model.md", self._report_model_snapshot + "\n")
        return self._report_model_snapshot

    def _infer_section_mode(
        self, title: str, outline_chunk: str, build_artifact: Optional[Dict[str, Any]]
    ) -> str:
        if build_artifact and str(build_artifact.get("writer_mode", "")).strip():
            return str(build_artifact["writer_mode"]).strip()

        combined = f"{title}\n{outline_chunk}".lower()
        debate_keywords = [
            "triển vọng",
            "dự báo",
            "định giá",
            "khuyến nghị",
            "rủi ro",
            "cảnh báo",
            "outlook",
            "valuation",
            "recommendation",
            "risk",
        ]
        if any(keyword in combined for keyword in debate_keywords):
            return "debate"
        return "direct"

    def _parse_sections(self, outline_text: str) -> List[SectionTask]:
        lines = outline_text.splitlines()
        section_starts = [i for i, line in enumerate(lines) if line.startswith("## ")]

        heading_prefix = "## "
        if not section_starts:
            section_starts = [
                i for i, line in enumerate(lines) if line.startswith("# ")
            ]
            heading_prefix = "# "

        sections: List[SectionTask] = []
        if not section_starts:
            text = outline_text.strip()
            sections.append(
                {
                    "index": 1,
                    "title": "Main Section",
                    "heading": "# Main Section",
                    "outline_chunk": text,
                    "dir_name": "section_1",
                }
            )
            return sections

        for idx, start in enumerate(section_starts, start=1):
            end = section_starts[idx] if idx < len(section_starts) else len(lines)
            chunk = "\n".join(lines[start:end]).strip()
            heading = lines[start].strip()
            title = heading[len(heading_prefix) :].strip()
            build_artifact = self._get_build_artifact_for_section(title, heading)
            sections.append(
                {
                    "index": idx,
                    "title": title,
                    "heading": heading,
                    "outline_chunk": chunk,
                    "dir_name": f"section_{idx}",
                    "writer_mode": self._infer_section_mode(
                        title, chunk, build_artifact
                    ),
                    "build_artifact": build_artifact,
                }
            )
        return sections

    def _create_agent_with_tools(self, system_prompt: str, tools: List[Any]):
        kwargs = {"model": self.model, "tools": tools}
        try:
            return create_agent(system_prompt=system_prompt, **kwargs)
        except TypeError:
            return create_agent(prompt=system_prompt, **kwargs)

    def _extract_json_payload(self, text: str, fallback: Any) -> Any:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        object_match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if object_match:
            try:
                return json.loads(object_match.group(0))
            except json.JSONDecodeError:
                pass

        array_match = re.search(r"\[.*\]", candidate, flags=re.DOTALL)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except json.JSONDecodeError:
                pass

        return fallback

    def _relative_to_workspace(self, path_str: str) -> str:
        workspace_path = Path(self._get_workspace_path() or "").resolve()
        try:
            resolved = Path(path_str).resolve()
            return str(resolved.relative_to(workspace_path)).replace(os.sep, "/")
        except Exception:
            return path_str

    def _run_stance_agent(
        self,
        section: SectionTask,
        evidence_pack: str,
        stance: str,
        revision_guidance: str = "",
    ) -> Dict[str, str]:
        system_prompt = self._bull_prompt if stance == "bull" else self._bear_prompt
        agent = self._create_agent_with_tools(
            system_prompt=system_prompt,
            tools=[
                query_knowledge_graph,
                query_graph_natural,
                get_content_by_source_urls,
            ],
        )

        guidance_block = (
            f"\nRevision guidance:\n{revision_guidance}\n" if revision_guidance else ""
        )
        report_model = self._report_model_snapshot or "No canonical report model."
        prompt = (
            f"Write the {stance} case for this report section.\n"
            f"Section title: {section['title']}\n"
            f"Section heading: {section['heading']}\n"
            f"Outline guidance:\n{section['outline_chunk']}\n"
            f"Evidence pack:\n{evidence_pack}\n"
            f"Canonical report model:\n{report_model}\n"
            f"{guidance_block}"
            "Requirements:\n"
            "- Query the knowledge graph for evidence.\n"
            "- Use the evidence pack as the default grounding source and only extend it with graph facts that are clearly relevant.\n"
            "- Prefer official/company/regulator sources and broker research PDFs for quantitative claims.\n"
            "- Do not rely on tertiary or generic explainer sources for key financial numbers.\n"
            "- Use specific facts, dates, and entities.\n"
            "- Every reference you keep must include a full URL.\n"
            "- Respond in Vietnamese.\n"
            "- Return markdown only.\n"
        )

        result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        content = ""
        if result.get("messages"):
            content = self._extract_text(result["messages"][-1].content).strip()
        output_name = "bull_case.md" if stance == "bull" else "bear_case.md"
        output_path = self._write_file(
            f"{section['dir_name']}/{output_name}", content + "\n"
        )
        return {"content": content, "path": output_path}

    def _is_title_section(self, section: SectionTask) -> bool:
        return "tiêu đề tổng quan" in section["title"].lower()

    def _merge_sources(
        self, *source_lists: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge and deduplicate source dictionaries by URL."""
        merged: List[Dict[str, Any]] = []
        seen = set()

        for source_list in source_lists:
            for source in source_list or []:
                if not isinstance(source, dict):
                    continue
                url = str(source.get("url", "")).strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                merged.append(
                    {
                        "url": url,
                        "title": str(source.get("title") or url).strip(),
                        "quality_tier": self._source_quality_tier(url),
                        "domain": self._get_source_domain(url),
                    }
                )

        return merged

    def _format_reference_lines(self, sources: List[Dict[str, Any]]) -> List[str]:
        """Render sources in a citation-friendly numbered format."""
        if not sources:
            return ["No explicit source URLs found."]

        lines: List[str] = []
        for idx, source in enumerate(sources, start=1):
            title = str(source.get("title") or source.get("url") or "").strip()
            url = str(source.get("url") or "").strip()
            lines.append(f"[{idx}] {title}: [{url}]({url})")
        return lines

    def _build_artifact_to_evidence_pack(
        self, section: SectionTask, artifact: Dict[str, Any]
    ) -> str:
        evidence_records = self._filter_evidence_records_by_quality(
            section, artifact.get("evidence_records", [])
        )
        coverage_matrix = artifact.get("coverage_matrix", [])
        research_plan = artifact.get("plan", [])
        report_model = self._report_model_snapshot or ""

        blocks: List[str] = [
            f"# Evidence Pack: {section['title']}",
            "",
            f"Section outline:\n{section['outline_chunk']}",
            "",
            f"Writer mode: {section.get('writer_mode', 'direct')}",
            "",
            self._source_policy_block().strip(),
            "",
        ]

        if isinstance(research_plan, list) and research_plan:
            blocks.extend(["## Research plan", ""])
            for item in research_plan:
                if not isinstance(item, dict):
                    continue
                subquery = str(item.get("subquery", "")).strip()
                rationale = str(item.get("rationale", "")).strip()
                if subquery:
                    line = f"- {subquery}"
                    if rationale:
                        line += f" | coverage: {rationale}"
                    blocks.append(line)
            blocks.append("")

        if isinstance(coverage_matrix, list) and coverage_matrix:
            blocks.extend(["## Coverage matrix", ""])
            for item in coverage_matrix:
                if not isinstance(item, dict):
                    continue
                point = str(item.get("point", "")).strip()
                status = str(item.get("status", "")).strip() or "unknown"
                support_count = int(item.get("support_count", 0) or 0)
                sample_facts = item.get("sample_facts", [])
                sample = ""
                if isinstance(sample_facts, list) and sample_facts:
                    sample = f" | sample: {str(sample_facts[0]).strip()}"
                if point:
                    blocks.append(
                        f"- {point} | status={status} | support_count={support_count}{sample}"
                    )
            blocks.append("")

        if isinstance(evidence_records, list) and evidence_records:
            blocks.extend(["## Structured evidence ledger", ""])
            for idx, record in enumerate(evidence_records[:30], start=1):
                if not isinstance(record, dict):
                    continue
                fact = str(record.get("facts", "")).strip()
                primary_url = str(record.get("primary_url", "")).strip()
                source_urls = record.get("source_urls", [])
                quality_tier = int(record.get("quality_tier", 0) or 0)
                source_line = ""
                if isinstance(source_urls, list) and source_urls:
                    source_line = ", ".join(
                        str(url).strip() for url in source_urls[:3] if str(url).strip()
                    )
                blocks.extend(
                    [
                        f"### Evidence {idx}",
                        f"Fact: {fact or 'N/A'}",
                        f"Primary source: {primary_url or 'N/A'}",
                        f"Source quality tier: {quality_tier}",
                        f"Supporting URLs: {source_line or primary_url or 'N/A'}",
                        "",
                    ]
                )

        if report_model:
            blocks.extend(["## Canonical report model", "", report_model.strip(), ""])

        return "\n".join(blocks).strip()

    def _fallback_evidence_queries(self, section: SectionTask) -> List[str]:
        queries: List[str] = []
        for line in section["outline_chunk"].splitlines():
            stripped = line.strip()
            if stripped.startswith("- **"):
                cleaned = re.sub(r"^- \*\*", "", stripped).replace("**", "").strip()
                cleaned = cleaned.rstrip(":").strip()
                if cleaned:
                    queries.append(
                        f"Tìm dữ liệu và luận điểm chính cho mục '{cleaned}' của phần '{section['title']}'"
                    )
        if not queries:
            queries = [
                f"Tóm tắt dữ liệu quan trọng cho phần '{section['title']}'",
                f"Các số liệu, xu hướng và rủi ro chính cho phần '{section['title']}'",
            ]
        return queries[: self.MAX_EVIDENCE_QUERIES]

    def _plan_evidence_queries(self, section: SectionTask) -> List[str]:
        prompt = (
            "Bạn đang lập kế hoạch truy vấn dữ liệu cho MỘT section của báo cáo tài chính.\n"
            "Hãy tạo 3 đến 4 câu hỏi truy vấn bằng tiếng Việt để phủ hết các ý trong outline.\n"
            "Mỗi truy vấn phải cụ thể, không chồng lặp, dễ tìm bằng knowledge graph.\n"
            "Trả về JSON array chỉ gồm string.\n\n"
            f"Section title:\n{section['title']}\n\n"
            f"Section outline:\n{section['outline_chunk']}\n"
        )
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content="Tạo danh sách truy vấn ngay."),
                ]
            )
            parsed = self._extract_json_payload(
                self._extract_text(response.content), fallback=[]
            )
        except Exception:
            parsed = []

        if not isinstance(parsed, list):
            return self._fallback_evidence_queries(section)

        queries = [str(item).strip() for item in parsed if str(item).strip()]
        return queries[: self.MAX_EVIDENCE_QUERIES] or self._fallback_evidence_queries(
            section
        )

    def _collect_section_evidence(self, section: SectionTask) -> str:
        build_artifact = section.get("build_artifact") or {}
        artifact_records = build_artifact.get("evidence_records", [])
        if isinstance(artifact_records, list) and artifact_records:
            evidence_pack = self._build_artifact_to_evidence_pack(
                section, build_artifact
            )
            self._write_file(f"{section['dir_name']}/evidence.md", evidence_pack + "\n")
            return evidence_pack

        queries = self._plan_evidence_queries(section)
        evidence_blocks: List[str] = [
            f"# Evidence Pack: {section['title']}",
            "",
            f"Section outline:\n{section['outline_chunk']}",
            "",
            self._source_policy_block().strip(),
            "",
        ]

        for idx, query in enumerate(queries, start=1):
            try:
                search_result = query_knowledge_graph.invoke(
                    {"query_type": "search", "query_value": query, "limit": 8}
                )
            except Exception as exc:
                search_result = {"context": f"Graph search failed: {exc}"}

            try:
                natural_result = query_graph_natural.invoke({"question": query})
            except Exception as exc:
                natural_result = {"context": f"Natural graph query failed: {exc}"}

            raw_query_sources = self._merge_sources(
                search_result.get("sources", []),
                natural_result.get("sources", []),
            )
            query_sources = self._filter_sources_by_quality(
                section, raw_query_sources, limit=6
            )
            source_excerpt = "No source excerpts retrieved."
            if query_sources:
                try:
                    source_content = get_content_by_source_urls.invoke(
                        {
                            "source_urls": [
                                source["url"] for source in query_sources[:4]
                            ],
                            "max_chunks_per_url": 2,
                        }
                    )
                    source_excerpt = str(
                        source_content.get("context", source_excerpt)
                    ).strip()
                except Exception as exc:
                    source_excerpt = f"Source content retrieval failed: {exc}"
            elif raw_query_sources:
                source_excerpt = (
                    "Retrieved sources were filtered out by source-quality policy."
                )

            evidence_blocks.extend(
                [
                    f"## Query {idx}",
                    f"Question: {query}",
                    "",
                    "### Graph facts",
                    str(search_result.get("context", "No graph facts found.")).strip(),
                    "",
                    "### Entity summaries",
                    str(
                        natural_result.get("context", "No entity summaries found.")
                    ).strip(),
                    "",
                    "### References",
                    "\n".join(self._format_reference_lines(query_sources)),
                    "",
                    "### Source excerpts",
                    source_excerpt,
                    "",
                ]
            )

        if self._report_model_snapshot:
            evidence_blocks.extend(
                [
                    "## Canonical report model",
                    "",
                    self._report_model_snapshot.strip(),
                    "",
                ]
            )

        evidence_pack = "\n".join(evidence_blocks).strip()
        self._write_file(f"{section['dir_name']}/evidence.md", evidence_pack + "\n")
        return evidence_pack

    def _extract_chart_specs(
        self,
        section: SectionTask,
        evidence_pack: str,
        bull_content: str,
        bear_content: str,
    ) -> List[Dict[str, Any]]:
        if self._is_title_section(section):
            return []

        prompt = (
            "You are deciding whether charts should be created for a report section.\n"
            "Return a JSON array with 0 to 2 chart specs.\n"
            "Each spec must include: title, ylabel, data, rationale.\n"
            "Rules:\n"
            "- Only include charts if the available evidence contains concrete numeric data.\n"
            "- Only include a chart if there are at least 3 explicit data points.\n"
            "- `data` must be a flat JSON object or simple list suitable for a chart.\n"
            "- Return JSON only.\n\n"
            f"Section title: {section['title']}\n\n"
            f"Evidence pack:\n{evidence_pack}\n\n"
            f"Bull content:\n{bull_content}\n\n"
            f"Bear content:\n{bear_content}\n"
        )
        response = self.model.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content="Create chart specs now."),
            ]
        )
        parsed = self._extract_json_payload(
            self._extract_text(response.content), fallback=[]
        )
        if not isinstance(parsed, list):
            return []
        specs: List[Dict[str, Any]] = []
        for item in parsed[: self.MAX_CHARTS_PER_SECTION]:
            if not isinstance(item, dict):
                continue
            if "title" not in item or "data" not in item:
                continue
            specs.append(item)
        return specs

    def _generate_chart(self, spec: Dict[str, Any]) -> str:
        chart_agent = self._create_agent_with_tools(
            system_prompt=self._chart_prompt,
            tools=[execute_chart_code, get_current_date, critique_chart],
        )
        best_path = ""
        best_score = -1.0
        critique_feedback = ""

        for attempt in range(1, self.MAX_CHART_REVISIONS + 1):
            prompt = (
                "Create a chart for this data.\n"
                f"Data: {json.dumps(spec.get('data', {}), ensure_ascii=False)}\n"
                f"Title: {spec.get('title', 'Chart')}\n"
                f"Y-Label: {spec.get('ylabel', '')}\n"
                f"Context: {spec.get('rationale', '')}\n"
            )
            if critique_feedback:
                prompt += (
                    "Previous critique to fix before regenerating:\n"
                    f"{critique_feedback}\n"
                )
            prompt += "Return only the chart file path."

            result = chart_agent.invoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )
            chart_path = ""
            if result.get("messages"):
                raw_output = self._extract_text(result["messages"][-1].content).strip()
                path_match = re.search(
                    r"([A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|webp))", raw_output
                )
                chart_path = path_match.group(1) if path_match else raw_output
            relative_path = self._relative_to_workspace(chart_path)
            if not relative_path or relative_path.startswith("Error"):
                continue

            absolute_path = Path(self._get_workspace_path() or "") / relative_path
            critique_raw = critique_chart.invoke(
                {
                    "image_path": str(absolute_path),
                    "context": spec.get("rationale", ""),
                }
            )
            critique = self._extract_json_payload(str(critique_raw), fallback={})
            score = float(critique.get("overall_score", 0) or 0)
            pass_threshold = bool(critique.get("pass_threshold", False))

            if score > best_score:
                best_score = score
                best_path = relative_path

            critique_payload_path = absolute_path.with_suffix(".critique.json")
            critique_payload_path.write_text(
                json.dumps(
                    critique or {"raw": critique_raw}, ensure_ascii=False, indent=2
                )
                + "\n",
                encoding="utf-8",
            )

            if pass_threshold:
                return relative_path

            critique_feedback = json.dumps(
                {
                    "overall_score": score,
                    "weaknesses": critique.get("weaknesses", []),
                    "suggestions": critique.get("suggestions", []),
                    "summary": critique.get("summary", ""),
                },
                ensure_ascii=False,
                indent=2,
            )

        return best_path

    def _synthesize_section(
        self,
        section: SectionTask,
        evidence_pack: str,
        bull_content: str,
        bear_content: str,
        chart_paths: List[str],
        revision_guidance: str = "",
    ) -> str:
        chart_block = "\n".join(
            f"![{section['title']} - chart {idx + 1}]({path})"
            for idx, path in enumerate(chart_paths)
            if path
        )
        report_model = self._report_model_snapshot or "No canonical report model."
        section_guidance = self._section_specific_guidance(section)
        response = self.model.invoke(
            [
                SystemMessage(
                    content=(
                        self._synth_prompt.replace(
                            "{current_date}", get_current_date.invoke({})
                        )
                        + "\n\nAdditional hard rules:\n"
                        + "- Write in Vietnamese.\n"
                        + "- Use only facts supported by the evidence pack, bull case, or bear case.\n"
                        + f"{self._source_policy_block()}\n"
                        + "- Preserve the exact section heading.\n"
                        + "- Do not collapse the section into a generic template if the outline contains specific bullets.\n"
                        + "- Prefer concrete numbers, dates, entities, and causal explanation over generic claims.\n"
                        + "- If evidence is missing for an outline point, keep it but state ngắn gọn rằng dữ liệu hiện chưa đủ.\n"
                        + "- Use a single consistent reference format: `[n] Tiêu đề: [url](url)`.\n"
                        + "- Avoid repeating generic `Key Drivers` or `Conclusion/Outlook` blocks unless the section style really needs them.\n"
                    )
                ),
                HumanMessage(
                    content=(
                        f"Write the final section draft in Vietnamese.\n"
                        f"Section title: {section['title']}\n"
                        f"Section heading: {section['heading']}\n"
                        f"Section outline:\n{section['outline_chunk']}\n\n"
                        f"Evidence pack:\n{evidence_pack}\n\n"
                        f"Canonical report model:\n{report_model}\n\n"
                        f"Bull case:\n{bull_content}\n\n"
                        f"Bear case:\n{bear_content}\n\n"
                        f"Available charts to embed:\n{chart_block or 'No charts'}\n\n"
                        f"Revision guidance:\n{revision_guidance or 'None'}\n\n"
                        f"Section-specific guidance:\n{section_guidance}\n"
                        "Return markdown only. Preserve the section heading exactly, produce a detailed section grounded in the evidence pack, "
                        "and include chart markdown only if the charts are genuinely supported."
                    )
                ),
            ]
        )
        return self._extract_text(response.content).strip()

    def _write_direct_section(
        self,
        section: SectionTask,
        evidence_pack: str,
        chart_paths: List[str],
        revision_guidance: str = "",
    ) -> str:
        chart_block = "\n".join(
            f"![{section['title']} - chart {idx + 1}]({path})"
            for idx, path in enumerate(chart_paths)
            if path
        )
        report_model = self._report_model_snapshot or "No canonical report model."
        section_guidance = self._section_specific_guidance(section)
        system_prompt = (
            "You write one grounded section of a Vietnamese financial research report.\n"
            "Use the evidence pack as the primary source of truth.\n"
            "Do not force a bull/bear structure unless the section itself is inherently about outlook, valuation, or risk.\n"
            "Every factual claim, number, date, and sourced statement must use inline citations like [1].\n"
            "End the section with ### References and a numbered reference list.\n"
            f"{self._source_policy_block()}\n"
            "Preserve the exact section heading.\n"
            "If evidence is thin for an outline point, say briefly that evidence is currently insufficient instead of filling with generic prose.\n"
            "Prefer concrete metrics, dates, named entities, and causal explanation over generic statements.\n"
            "Use one consistent reference format: `[n] Tiêu đề: [url](url)`.\n"
            "Avoid appending generic `Key Drivers` or `Conclusion/Outlook` blocks unless the outline explicitly calls for them.\n"
        )
        response = self.model.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=(
                        f"Write the final section draft in Vietnamese.\n"
                        f"Section title: {section['title']}\n"
                        f"Section heading: {section['heading']}\n"
                        f"Section outline:\n{section['outline_chunk']}\n\n"
                        f"Evidence pack:\n{evidence_pack}\n\n"
                        f"Canonical report model:\n{report_model}\n\n"
                        f"Available charts to embed:\n{chart_block or 'No charts'}\n\n"
                        f"Revision guidance:\n{revision_guidance or 'None'}\n\n"
                        f"Section-specific guidance:\n{section_guidance}\n"
                        "Return markdown only. Keep the section grounded, specific, and structurally faithful to the outline."
                    )
                ),
            ]
        )
        return self._extract_text(response.content).strip()

    def _critique_section(
        self, section: SectionTask, evidence_pack: str, draft_content: str
    ) -> Dict[str, Any]:
        prompt = (
            f"{self._critique_prompt}\n\n"
            "Evaluate exactly one section and return JSON only.\n"
            "Be strict on outline coverage, factual specificity, unsupported claims, and whether the section stayed faithful to the requested structure.\n"
            f"Section title: {section['title']}\n\n"
            f"Section outline:\n{section['outline_chunk']}\n\n"
            f"Evidence pack:\n{evidence_pack}\n\n"
            f"Draft content:\n{draft_content}\n"
        )
        response = self.model.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content="Return the critique JSON."),
            ]
        )
        critique = self._extract_json_payload(
            self._extract_text(response.content),
            fallback={
                "overall_score": 6.0,
                "pass_threshold": False,
                "section_scores": [
                    {
                        "section_title": section["title"],
                        "score": 6.0,
                        "strengths": [],
                        "weaknesses": ["Could not parse critique response."],
                        "needs_revision": True,
                        "revision_guidance": "Bổ sung thêm dữ liệu cụ thể, bám sát outline gốc, loại bỏ nhận định chung chung và chỉ giữ các luận điểm có bằng chứng.",
                    }
                ],
                "sections_needing_revision": [section["title"]],
                "summary": "Không phân tích được critique chuẩn; nên chỉnh sửa section này.",
            },
        )
        return critique

    def _draft_section(
        self, section: SectionTask, revision_guidance: str = ""
    ) -> SectionResult:
        evidence_pack = self._collect_section_evidence(section)
        writer_mode = str(section.get("writer_mode", "direct")).strip() or "direct"
        bull_result = {"content": "", "path": ""}
        bear_result = {"content": "", "path": ""}

        if writer_mode == "debate":
            with ThreadPoolExecutor(max_workers=2) as executor:
                bull_future = executor.submit(
                    wrap_with_current_tracing_context(self._run_stance_agent),
                    section,
                    evidence_pack,
                    "bull",
                    revision_guidance,
                )
                bear_future = executor.submit(
                    wrap_with_current_tracing_context(self._run_stance_agent),
                    section,
                    evidence_pack,
                    "bear",
                    revision_guidance,
                )
                bull_result = bull_future.result()
                bear_result = bear_future.result()

        chart_specs = self._extract_chart_specs(
            section, evidence_pack, bull_result["content"], bear_result["content"]
        )
        chart_paths: List[str] = []
        if chart_specs:
            with ThreadPoolExecutor(
                max_workers=min(len(chart_specs), self.MAX_CHARTS_PER_SECTION)
            ) as executor:
                chart_futures = [
                    executor.submit(
                        wrap_with_current_tracing_context(self._generate_chart), spec
                    )
                    for spec in chart_specs
                ]
                for future in as_completed(chart_futures):
                    chart_path = future.result()
                    if chart_path and not chart_path.startswith("Error"):
                        chart_paths.append(chart_path)

        if writer_mode == "debate":
            draft_content = self._synthesize_section(
                section=section,
                evidence_pack=evidence_pack,
                bull_content=bull_result["content"],
                bear_content=bear_result["content"],
                chart_paths=chart_paths,
                revision_guidance=revision_guidance,
            )
        else:
            draft_content = self._write_direct_section(
                section=section,
                evidence_pack=evidence_pack,
                chart_paths=chart_paths,
                revision_guidance=revision_guidance,
            )
        draft_path = self._write_file(
            f"{section['dir_name']}/draft.md", draft_content + "\n"
        )

        return {
            "index": section["index"],
            "title": section["title"],
            "dir_name": section["dir_name"],
            "evidence_path": str(
                Path(self._get_workspace_path() or "")
                / section["dir_name"]
                / "evidence.md"
            ),
            "bull_case_path": bull_result["path"],
            "bear_case_path": bear_result["path"],
            "draft_path": draft_path,
            "evidence_pack": evidence_pack,
            "draft": draft_content,
            "writer_mode": writer_mode,
        }

    def _draft_sections_node(self, state: WriteState) -> Dict[str, Any]:
        sections = state.get("sections", [])
        if not sections:
            outline = self._read_outline()
            sections = self._parse_sections(outline)
        self._ensure_report_model_snapshot(sections)

        results: List[SectionResult] = []
        with ThreadPoolExecutor(max_workers=max(1, len(sections))) as executor:
            future_map = {
                executor.submit(
                    wrap_with_current_tracing_context(self._draft_section), section
                ): section
                for section in sections
            }
            for future in as_completed(future_map):
                results.append(future.result())

        results.sort(key=lambda item: item["index"])
        return {
            "outline": self._read_outline(),
            "sections": sections,
            "section_results": results,
            "critique_round": 1,
        }

    def _critique_sections_node(self, state: WriteState) -> Dict[str, Any]:
        sections = state.get("sections", [])
        results = state.get("section_results", [])
        section_by_index = {section["index"]: section for section in sections}
        critiques: List[SectionResult] = []

        with ThreadPoolExecutor(max_workers=max(1, len(results))) as executor:
            future_map = {
                executor.submit(
                    wrap_with_current_tracing_context(self._critique_section),
                    section_by_index[result["index"]],
                    result.get("evidence_pack", ""),
                    result.get("draft", ""),
                ): result
                for result in results
            }
            for future in as_completed(future_map):
                result = future_map[future]
                critique = future.result()
                critique_path = self._write_file(
                    f"{result['dir_name']}/critique.json",
                    json.dumps(critique, ensure_ascii=False, indent=2) + "\n",
                )
                updated = dict(result)
                updated["critique"] = critique
                updated["critique_path"] = critique_path
                critiques.append(updated)

        critiques.sort(key=lambda item: item["index"])

        weak_sections: List[Dict[str, Any]] = []
        numeric_scores: List[float] = []
        for item in critiques:
            critique = item.get("critique", {})
            section_scores = critique.get("section_scores", [])
            if section_scores:
                score = float(section_scores[0].get("score", 0))
                numeric_scores.append(score)
                needs_revision = bool(section_scores[0].get("needs_revision", False))
                if needs_revision or score < 7:
                    weak_sections.append(
                        {
                            "index": item["index"],
                            "title": item["title"],
                            "revision_guidance": section_scores[0].get(
                                "revision_guidance",
                                "Bổ sung chiều sâu phân tích và nguồn trích dẫn.",
                            ),
                        }
                    )

        overall_score = (
            sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0
        )
        pass_threshold = overall_score >= 8 and not weak_sections

        return {
            "section_results": critiques,
            "sections_needing_revision": weak_sections,
            "pass_threshold": pass_threshold,
        }

    def _revise_sections_node(self, state: WriteState) -> Dict[str, Any]:
        revisions = state.get("sections_needing_revision", [])
        sections = state.get("sections", [])
        prior_results = {
            result["index"]: result for result in state.get("section_results", [])
        }
        section_by_index = {section["index"]: section for section in sections}

        revised_results: Dict[int, SectionResult] = dict(prior_results)
        with ThreadPoolExecutor(max_workers=max(1, len(revisions))) as executor:
            future_map = {
                executor.submit(
                    wrap_with_current_tracing_context(self._draft_section),
                    section_by_index[revision["index"]],
                    revision.get("revision_guidance", ""),
                ): revision
                for revision in revisions
            }
            for future in as_completed(future_map):
                result = future.result()
                revised_results[result["index"]] = result

        ordered = [revised_results[idx] for idx in sorted(revised_results)]
        return {
            "section_results": ordered,
            "critique_round": state.get("critique_round", 1) + 1,
        }

    def _route_after_critique(self, state: WriteState) -> str:
        critique_round = state.get("critique_round", 1)
        if state.get("pass_threshold", False):
            return "finalize"
        if critique_round >= self.MAX_CRITIQUE_ROUNDS:
            return "finalize"
        if not state.get("sections_needing_revision"):
            return "finalize"
        return "revise_sections"

    def _finalize_node(self, state: WriteState) -> Dict[str, Any]:
        section_results = state.get("section_results", [])
        summary_lines = ["DONE", ""]
        for result in section_results:
            critique = result.get("critique", {})
            section_scores = critique.get("section_scores", [])
            score = section_scores[0].get("score", "n/a") if section_scores else "n/a"
            summary_lines.append(
                f"- section_{result['index']}: {result['title']} | score={score} | {result['draft_path']}"
            )
        return {"messages": [AIMessage(content="\n".join(summary_lines))]}

    def create(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph is required for the write phase but is not installed. "
                "Add the `langgraph` package to the environment before running phase=write."
            ) from exc

        self._get_workspace_path()
        set_current_session_id(self.session_id)

        graph = StateGraph(WriteState)
        graph.add_node("draft_sections", self._draft_sections_node)
        graph.add_node("critique_sections", self._critique_sections_node)
        graph.add_node("revise_sections", self._revise_sections_node)
        graph.add_node("finalize", self._finalize_node)

        graph.add_edge(START, "draft_sections")
        graph.add_edge("draft_sections", "critique_sections")
        graph.add_conditional_edges(
            "critique_sections",
            self._route_after_critique,
            {
                "revise_sections": "revise_sections",
                "finalize": "finalize",
            },
        )
        graph.add_edge("revise_sections", "critique_sections")
        graph.add_edge("finalize", END)

        self._agent = LangGraphWriteAgent(
            graph=graph.compile(),
            workspace_path=self._workspace_path,
            session_id=self.session_id,
        )
        return self._agent

    @property
    def agent(self):
        if self._agent is None:
            self.create()
        return self._agent


def create_writer_orchestrator(
    model: BaseChatModel,
    session_id: Optional[str] = None,
    output_base_path: str = "outputs",
):
    orchestrator = WriterOrchestrator(
        model=model,
        session_id=session_id,
        output_base_path=output_base_path,
    )
    return orchestrator.create()
