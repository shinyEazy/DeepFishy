import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from engine.tools.critique_chart import critique_chart
from engine.tools.execute_chart_code import execute_chart_code
from engine.tools.get_content_by_source_urls import get_content_by_source_urls
from engine.tools.get_current_date import get_current_date
from engine.tools.query_knowledge_graph import (
    query_graph_natural,
    query_knowledge_graph,
)
from engine.tools.search_and_build_graph import set_current_session_id


class SectionTask(TypedDict):
    index: int
    title: str
    heading: str
    outline_chunk: str
    dir_name: str


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
    MAX_EVIDENCE_QUERIES = 4

    def __init__(
        self,
        model: BaseChatModel,
        session_id: Optional[str] = None,
        group_id: Optional[str] = None,
        output_base_path: str = "outputs",
    ):
        self.model = model
        self.session_id = session_id
        self.group_id = group_id or session_id or "default_session"
        self.output_base_path = output_base_path
        self._agent = None
        self._workspace_path = None
        self._bull_prompt = self._load_prompt("bull_agent.md")
        self._bear_prompt = self._load_prompt("bear_agent.md")
        self._critique_prompt = self._load_prompt("critique_agent.md")
        self._chart_prompt = self._load_prompt("chart_generator.md")
        self._synth_prompt = self._load_synth_prompt()

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
            sections.append(
                {
                    "index": idx,
                    "title": title,
                    "heading": heading,
                    "outline_chunk": chunk,
                    "dir_name": f"section_{idx}",
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
        prompt = (
            f"Write the {stance} case for this report section.\n"
            f"Section title: {section['title']}\n"
            f"Section heading: {section['heading']}\n"
            f"Outline guidance:\n{section['outline_chunk']}\n"
            f"Evidence pack:\n{evidence_pack}\n"
            f"{guidance_block}"
            "Requirements:\n"
            "- Query the knowledge graph for evidence.\n"
            "- Use the evidence pack as the default grounding source and only extend it with graph facts that are clearly relevant.\n"
            "- Use specific facts, dates, and entities.\n"
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
        queries = self._plan_evidence_queries(section)
        evidence_blocks: List[str] = [
            f"# Evidence Pack: {section['title']}",
            "",
            f"Section outline:\n{section['outline_chunk']}",
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

            query_sources = self._merge_sources(
                search_result.get("sources", []),
                natural_result.get("sources", []),
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
        prompt = (
            "Create a chart for this data.\n"
            f"Data: {json.dumps(spec.get('data', {}), ensure_ascii=False)}\n"
            f"Title: {spec.get('title', 'Chart')}\n"
            f"Y-Label: {spec.get('ylabel', '')}\n"
            f"Context: {spec.get('rationale', '')}\n"
            "Return only the chart file path."
        )
        result = chart_agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        chart_path = ""
        if result.get("messages"):
            chart_path = self._extract_text(result["messages"][-1].content).strip()
        return self._relative_to_workspace(chart_path)

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
        title_specific_rule = (
            "This is the overview title section. Write a concise opening with a specific title and 2 short paragraphs. Do not invent charts or generic 'Key Drivers' blocks.\n"
            if self._is_title_section(section)
            else "Follow the section outline closely. Preserve the subsection bullets/themes from the outline and expand them with supported analysis.\n"
        )
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
                        + "- Preserve the exact section heading.\n"
                        + "- Do not collapse the section into a generic template if the outline contains specific bullets.\n"
                        + "- Prefer concrete numbers, dates, entities, and causal explanation over generic claims.\n"
                        + "- If evidence is missing for an outline point, keep it but state ngắn gọn rằng dữ liệu hiện chưa đủ.\n"
                    )
                ),
                HumanMessage(
                    content=(
                        f"Write the final section draft in Vietnamese.\n"
                        f"Section title: {section['title']}\n"
                        f"Section heading: {section['heading']}\n"
                        f"Section outline:\n{section['outline_chunk']}\n\n"
                        f"Evidence pack:\n{evidence_pack}\n\n"
                        f"Bull case:\n{bull_content}\n\n"
                        f"Bear case:\n{bear_content}\n\n"
                        f"Available charts to embed:\n{chart_block or 'No charts'}\n\n"
                        f"Revision guidance:\n{revision_guidance or 'None'}\n\n"
                        f"{title_specific_rule}"
                        "Return markdown only. Preserve the section heading exactly, produce a detailed section grounded in the evidence pack, "
                        "and include chart markdown only if the charts are genuinely supported."
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
        with ThreadPoolExecutor(max_workers=2) as executor:
            bull_future = executor.submit(
                self._run_stance_agent,
                section,
                evidence_pack,
                "bull",
                revision_guidance,
            )
            bear_future = executor.submit(
                self._run_stance_agent,
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
                    executor.submit(self._generate_chart, spec) for spec in chart_specs
                ]
                for future in as_completed(chart_futures):
                    chart_path = future.result()
                    if chart_path and not chart_path.startswith("Error"):
                        chart_paths.append(chart_path)

        draft_content = self._synthesize_section(
            section=section,
            evidence_pack=evidence_pack,
            bull_content=bull_result["content"],
            bear_content=bear_result["content"],
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
        }

    def _draft_sections_node(self, state: WriteState) -> Dict[str, Any]:
        sections = state.get("sections", [])
        if not sections:
            outline = self._read_outline()
            sections = self._parse_sections(outline)

        results: List[SectionResult] = []
        with ThreadPoolExecutor(max_workers=max(1, len(sections))) as executor:
            future_map = {
                executor.submit(self._draft_section, section): section
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
                    self._critique_section,
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
        pass_threshold = overall_score >= 9 and not weak_sections

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
                    self._draft_section,
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
        set_current_session_id(self.group_id)

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
    group_id: Optional[str] = None,
    output_base_path: str = "outputs",
):
    orchestrator = WriterOrchestrator(
        model=model,
        session_id=session_id,
        group_id=group_id,
        output_base_path=output_base_path,
    )
    return orchestrator.create()
