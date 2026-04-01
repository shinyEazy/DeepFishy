import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.logging import logger
from engine.tools.normalizer import (
    _load_staged_records,
    commit_facts_to_graph,
    get_finance_data_normalized,
    search_local_normalized,
    search_web_normalized,
)
from engine.tools.search_and_build_graph import (
    clear_pending_graph_updates,
    set_current_session_id,
)


class TemplateSection(TypedDict):
    section_id: str
    section_title: str
    heading_line: str
    body: str
    is_parallel_section: bool


class ResearchTask(TypedDict):
    task_id: str
    section_id: str
    section_title: str
    subquery: str
    tool_hint: str
    rationale: str


class CritiqueResult(TypedDict):
    sufficient: bool
    missing_points: List[str]
    follow_up_queries: List[str]
    reasoning: str
    coverage_matrix: List[Dict[str, Any]]


class EvidenceRecord(TypedDict, total=False):
    section_id: str
    facts: str
    source_urls: List[str]
    primary_url: str
    date_ts: int
    category: str
    score: float


class SectionWorkflowResult(TypedDict):
    section_id: str
    section_title: str
    plan: List[ResearchTask]
    research_results: List[Dict[str, str]]
    critique: CritiqueResult
    evidence_records: List[EvidenceRecord]
    writer_mode: str
    rewritten_section: str


class BuildState(TypedDict, total=False):
    messages: list
    user_request: str
    template_outline: str
    template_prefix: str
    template_sections: List[TemplateSection]
    parallel_sections: List[TemplateSection]
    section_results: List[SectionWorkflowResult]
    outline: str


_RESEARCHER_SYSTEM_PROMPT = """
You are the Researcher, a focused single-purpose agent. You receive ONE specific research sub-query and your goal is to find sufficient, high-quality factual data for it, then stage the findings for batch knowledge graph ingestion.

Available tools:
- search_local_normalized
- search_web_normalized
- get_finance_data_normalized
- commit_facts_to_graph

Workflow:
1. Choose the appropriate search tool(s) based on the sub-query.
2. Gather only facts directly relevant to the sub-query.
3. Track the source URLs returned by the tools.
4. If needed, refine repeatedly, but stay within the same sub-query and stop only when coverage is sufficient or the tool budget is exhausted.
5. Call commit_facts_to_graph exactly once with:
   - facts
   - source_urls
   - section_id
6. Reply with:

EXTRACTION COMPLETE
- Sub-query: ...
- Sources: ...
- Staged records: ...
- Key facts: ...

Rules:
- One sub-query only.
- Maximum 6 total search/data tool calls before commit.
- Prefer official company disclosures, regulator sources, and broker research PDFs for important quantitative claims.
- Do not rely on tertiary explainers, forums, student notes, or generic aggregator pages for key financial facts if better sources are available.
- If you only find weak sources, keep searching within budget and note the source-quality limitation in your final summary.
- Never hallucinate.
- Always call commit_facts_to_graph exactly once if you found any relevant facts.
""".strip()


class LangGraphBuildAgent:
    """Small wrapper so the LangGraph build flow matches the existing invoke contract."""

    def __init__(self, graph, workspace_path: Optional[str], session_id: Optional[str]):
        self._graph = graph
        self._workspace_path = workspace_path
        self._session_id = session_id
        self._expects_task_delegation = False

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        messages = payload.get("messages", [])
        return self._graph.invoke({"messages": messages})


class BuilderOrchestrator:
    """
    Build-phase orchestrator implemented as a LangGraph workflow.

    Flow:
    1. Parse the selected template into sections.
    2. Run each numbered section as an independent workflow in parallel.
    3. Inside each section workflow: plan sub-queries, research in parallel,
       critique coverage, optionally fill gaps, then rewrite that section.
    4. Merge section outputs back into the template and hand off for graph usage.
    """

    MAX_SECTION_SUBQUERIES = 6
    MAX_FOLLOW_UP_QUERIES = 3
    MAX_SECTION_EVIDENCE_RECORDS = 40

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

    def _extract_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: List[str] = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    text_parts.append(str(block["text"]))
                elif isinstance(block, str):
                    text_parts.append(block)
            return "\n".join(text_parts)
        return str(content)

    def _get_workspace_path(self) -> Optional[str]:
        if not self.session_id:
            return None
        if self._workspace_path is None:
            self._workspace_path = os.path.join(self.output_base_path, self.session_id)
            os.makedirs(self._workspace_path, exist_ok=True)
        return self._workspace_path

    def _write_workspace_file(self, filename: str, content: str) -> None:
        workspace_path = self._get_workspace_path()
        if not workspace_path:
            return
        path = Path(workspace_path) / filename
        path.write_text(content, encoding="utf-8")
        logger.info(f"Builder wrote {filename} to {path}")

    def _extract_user_request_and_template(self, user_message: str) -> tuple[str, str]:
        marker = "Vui lòng sử dụng template outline sau đây làm cơ sở cấu trúc khi xây dựng report outline cuối cùng:"
        if marker not in user_message:
            return user_message.strip(), ""

        topic, template = user_message.split(marker, 1)
        return topic.strip(), template.strip()

    def _split_template_sections(self, template_outline: str) -> List[TemplateSection]:
        if not template_outline.strip():
            return [
                {
                    "section_id": "section_1",
                    "section_title": "Main Section",
                    "heading_line": "## Main Section",
                    "body": "",
                    "is_parallel_section": True,
                }
            ]

        headings = list(
            re.finditer(r"^##\s+(.+)$", template_outline, flags=re.MULTILINE)
        )
        if not headings:
            return [
                {
                    "section_id": "section_1",
                    "section_title": "Main Section",
                    "heading_line": "## Main Section",
                    "body": template_outline.strip(),
                    "is_parallel_section": True,
                }
            ]

        sections: List[TemplateSection] = []
        numbered_idx = 0
        for idx, match in enumerate(headings):
            title = match.group(1).strip()
            heading_line = match.group(0).strip()
            body_start = match.end()
            body_end = (
                headings[idx + 1].start()
                if idx + 1 < len(headings)
                else len(template_outline)
            )
            body = template_outline[body_start:body_end].strip("\n")
            is_parallel = bool(re.match(r"^\d+\.", title))
            if is_parallel:
                numbered_idx += 1
                section_id = f"section_{numbered_idx}"
            else:
                section_id = "title_section"

            sections.append(
                {
                    "section_id": section_id,
                    "section_title": title,
                    "heading_line": heading_line,
                    "body": body.strip(),
                    "is_parallel_section": is_parallel,
                }
            )

        return sections

    def _extract_template_prefix(self, template_outline: str) -> str:
        match = re.search(r"^##\s+.+$", template_outline, flags=re.MULTILINE)
        if not match:
            return ""
        return template_outline[: match.start()].strip()

    def _extract_json_array(self, text: str) -> List[Dict[str, Any]]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)

        match = re.search(r"\[\s*\{.*\}\s*\]", candidate, flags=re.DOTALL)
        if match:
            candidate = match.group(0)

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)

        match = re.search(r"\{\s*.*\s*\}", candidate, flags=re.DOTALL)
        if match:
            candidate = match.group(0)

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _extract_section_focus_points(self, section: TemplateSection) -> List[str]:
        points: List[str] = []
        for raw_line in section.get("body", "").splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("- **"):
                continue
            cleaned = re.sub(r"^- \*\*", "", stripped)
            cleaned = cleaned.replace("**", "").strip()
            cleaned = cleaned.rstrip(":").strip()
            if cleaned:
                points.append(cleaned)

        if not points:
            return [section["section_title"]]
        return points

    def _load_section_evidence_records(self, section_id: str) -> List[EvidenceRecord]:
        records: List[EvidenceRecord] = []
        seen = set()

        for record in _load_staged_records():
            if str(record.get("section_id", "")).strip() != section_id:
                continue

            fact = str(record.get("facts", "")).strip()
            primary_url = str(record.get("primary_url", "")).strip()
            key = (fact, primary_url)
            if not fact or key in seen:
                continue
            seen.add(key)

            source_urls = record.get("source_urls", [])
            if not isinstance(source_urls, list):
                source_urls = []

            records.append(
                {
                    "section_id": section_id,
                    "facts": fact,
                    "source_urls": [
                        str(url).strip() for url in source_urls if str(url).strip()
                    ],
                    "primary_url": primary_url,
                    "date_ts": int(record.get("date_ts", 0) or 0),
                    "category": str(record.get("category", "")).strip(),
                    "score": float(record.get("score", 1.0) or 1.0),
                }
            )

        records.sort(
            key=lambda item: (
                -float(item.get("score", 1.0) or 1.0),
                str(item.get("facts", "")),
            )
        )
        return records[: self.MAX_SECTION_EVIDENCE_RECORDS]

    def _infer_writer_mode(self, section: TemplateSection) -> str:
        combined = (
            f"{section.get('section_title', '')}\n{section.get('heading_line', '')}\n{section.get('body', '')}"
        ).lower()
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

    def _fallback_section_plan(
        self,
        user_request: str,
        section: TemplateSection,
        prefix: str = "task",
    ) -> List[ResearchTask]:
        lines = [
            ln.strip() for ln in section.get("body", "").splitlines() if ln.strip()
        ]
        coverage_points: List[str] = []
        for line in lines:
            if line.startswith("- **"):
                cleaned = re.sub(r"^- \*\*", "", line).strip()
                cleaned = cleaned.replace("**", "").strip()
                cleaned = cleaned.rstrip(":").strip()
                if cleaned:
                    coverage_points.append(cleaned)
        if not coverage_points:
            coverage_points = [
                f"boi canh tong quan cho {section['section_title']}",
                f"so lieu then chot cho {section['section_title']}",
                f"dong luc va rui ro cho {section['section_title']}",
            ]

        tasks: List[ResearchTask] = []
        for idx, point in enumerate(
            coverage_points[: self.MAX_SECTION_SUBQUERIES], start=1
        ):
            query = (
                f"{user_request} - tim du lieu cu the de phu hop muc '{point}' "
                f"thuoc phan '{section['section_title']}'"
            )
            tasks.append(
                {
                    "task_id": f"{section['section_id']}_{prefix}_{idx}",
                    "section_id": section["section_id"],
                    "section_title": section["section_title"],
                    "subquery": query,
                    "tool_hint": "mixed",
                    "rationale": point,
                }
            )
        return tasks

    def _normalize_section_plan(
        self,
        items: List[Dict[str, Any]],
        user_request: str,
        section: TemplateSection,
        prefix: str = "task",
    ) -> List[ResearchTask]:
        tasks: List[ResearchTask] = []
        for idx, item in enumerate(items, start=1):
            subquery = str(item.get("subquery", "")).strip()
            if not subquery:
                continue
            tool_hint = str(item.get("tool_hint", "mixed")).strip() or "mixed"
            rationale = (
                str(item.get("rationale", "")).strip() or f"coverage point {idx}"
            )
            tasks.append(
                {
                    "task_id": f"{section['section_id']}_{prefix}_{len(tasks) + 1}",
                    "section_id": section["section_id"],
                    "section_title": section["section_title"],
                    "subquery": subquery,
                    "tool_hint": tool_hint,
                    "rationale": rationale,
                }
            )

        if not tasks:
            return self._fallback_section_plan(user_request, section, prefix=prefix)
        return tasks[: self.MAX_SECTION_SUBQUERIES]

    def _plan_section_queries(
        self,
        user_request: str,
        section: TemplateSection,
        prefix: str = "task",
        missing_points: Optional[List[str]] = None,
    ) -> List[ResearchTask]:
        requested_focus = ""
        focus_points = self._extract_section_focus_points(section)
        if missing_points:
            requested_focus = (
                "\nMissing coverage points that must be addressed:\n"
                + json.dumps(missing_points, ensure_ascii=False, indent=2)
            )

        planner_prompt = (
            "You are planning research for ONE report section.\n"
            "Create 3 to 6 narrow subqueries that together cover the section template.\n"
            "Return JSON array only.\n"
            "Each object must contain: subquery, tool_hint, rationale.\n"
            "tool_hint must be one of: local, web, finance, mixed.\n"
            "Every subquery must be written in Vietnamese.\n"
            "Subqueries must be non-overlapping and directly tied to the section outline.\n\n"
            f"User topic:\n{user_request}\n\n"
            f"Section heading:\n{section['heading_line']}\n\n"
            f"Section outline body:\n{section['body']}\n\n"
            f"Section coverage points:\n{json.dumps(focus_points, ensure_ascii=False, indent=2)}{requested_focus}"
        )

        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=planner_prompt),
                    HumanMessage(content="Create the section research plan now."),
                ]
            )
            items = self._extract_json_array(self._extract_text(response.content))
        except Exception as exc:
            logger.warning(f"Section planner failed for {section['section_id']}: {exc}")
            items = []

        return self._normalize_section_plan(
            items,
            user_request=user_request,
            section=section,
            prefix=prefix,
        )

    def _create_researcher_agent(self):
        kwargs = {
            "model": self.model,
            "tools": [
                search_local_normalized,
                search_web_normalized,
                get_finance_data_normalized,
                commit_facts_to_graph,
            ],
        }
        try:
            return create_agent(system_prompt=_RESEARCHER_SYSTEM_PROMPT, **kwargs)
        except TypeError:
            return create_agent(prompt=_RESEARCHER_SYSTEM_PROMPT, **kwargs)

    def _run_research_task(self, task: ResearchTask) -> Dict[str, str]:
        researcher = self._create_researcher_agent()
        prompt = (
            f"Research this single sub-query and stage the facts.\n"
            f"Sub-query: {task['subquery']}\n"
            f"Section ID: {task['section_id']}\n"
            f"Section title: {task['section_title']}\n"
            f"Tool hint: {task['tool_hint']}\n"
            f"Coverage goal: {task['rationale']}\n"
            "Call commit_facts_to_graph exactly once after collecting the relevant facts."
        )

        try:
            result = researcher.invoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )
            final_message = ""
            if result.get("messages"):
                final_message = self._extract_text(result["messages"][-1].content)
            return {
                "task_id": task["task_id"],
                "section_id": task["section_id"],
                "section_title": task["section_title"],
                "subquery": task["subquery"],
                "rationale": task["rationale"],
                "status": "completed",
                "summary": final_message.strip(),
            }
        except Exception as exc:
            logger.error(
                f"Research task failed for {task['task_id']} ({task['subquery']}): {exc}",
                exc_info=True,
            )
            return {
                "task_id": task["task_id"],
                "section_id": task["section_id"],
                "section_title": task["section_title"],
                "subquery": task["subquery"],
                "rationale": task["rationale"],
                "status": "error",
                "summary": f"Research failed: {exc}",
            }

    def _run_tasks_parallel(self, tasks: List[ResearchTask]) -> List[Dict[str, str]]:
        if not tasks:
            return []

        results: List[Dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, len(tasks))) as executor:
            futures = {
                executor.submit(self._run_research_task, task): task for task in tasks
            }
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item.get("task_id", ""))
        return results

    def _critique_section_coverage(
        self,
        user_request: str,
        section: TemplateSection,
        research_results: List[Dict[str, str]],
        evidence_records: List[EvidenceRecord],
    ) -> CritiqueResult:
        coverage_points = self._extract_section_focus_points(section)
        evidence_snapshot = [
            {
                "fact": record.get("facts", ""),
                "primary_url": record.get("primary_url", ""),
                "source_urls": record.get("source_urls", []),
            }
            for record in evidence_records[:20]
        ]
        critique_prompt = (
            "You are a critique agent for section-level research coverage.\n"
            "Evaluate whether the collected research is sufficient to cover the full section outline.\n"
            "Return JSON object only with keys: sufficient, missing_points, follow_up_queries, reasoning, coverage_matrix.\n"
            "- sufficient: boolean\n"
            "- missing_points: array of uncovered outline points\n"
            "- follow_up_queries: array of at most 3 narrow additional queries written in Vietnamese\n"
            "- reasoning: short explanation\n\n"
            "- coverage_matrix: array of objects with keys point, status, support_count, sample_facts\n"
            "Only mark sufficient=true if every coverage point has at least one source-backed fact or is explicitly marked as partially covered with a justified reason.\n\n"
            "Evidence backed only by generic explainers, student notes, forum-like sources, or obviously mismatched-company sources should be treated as weak or missing.\n\n"
            f"User topic:\n{user_request}\n\n"
            f"Section heading:\n{section['heading_line']}\n\n"
            f"Section outline body:\n{section['body']}\n\n"
            f"Section coverage points:\n{json.dumps(coverage_points, ensure_ascii=False, indent=2)}\n\n"
            f"Research results:\n{json.dumps(research_results, ensure_ascii=False, indent=2)}\n\n"
            f"Structured evidence ledger:\n{json.dumps(evidence_snapshot, ensure_ascii=False, indent=2)}"
        )

        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=critique_prompt),
                    HumanMessage(content="Critique the section coverage now."),
                ]
            )
            parsed = self._extract_json_object(self._extract_text(response.content))
        except Exception as exc:
            logger.warning(
                f"Section critique failed for {section['section_id']}: {exc}"
            )
            parsed = {}

        sufficient = bool(parsed.get("sufficient", False))
        missing_points = parsed.get("missing_points", [])
        follow_up_queries = parsed.get("follow_up_queries", [])
        coverage_matrix = parsed.get("coverage_matrix", [])

        if not isinstance(missing_points, list):
            missing_points = []
        if not isinstance(follow_up_queries, list):
            follow_up_queries = []
        if not isinstance(coverage_matrix, list):
            coverage_matrix = []

        normalized_coverage: List[Dict[str, Any]] = []
        for point in coverage_matrix:
            if not isinstance(point, dict):
                continue
            normalized_coverage.append(
                {
                    "point": str(point.get("point", "")).strip(),
                    "status": str(point.get("status", "")).strip() or "missing",
                    "support_count": int(point.get("support_count", 0) or 0),
                    "sample_facts": (
                        [
                            str(item).strip()
                            for item in point.get("sample_facts", [])[:2]
                            if str(item).strip()
                        ]
                        if isinstance(point.get("sample_facts", []), list)
                        else []
                    ),
                }
            )

        if not normalized_coverage:
            normalized_coverage = [
                {
                    "point": point,
                    "status": "missing",
                    "support_count": 0,
                    "sample_facts": [],
                }
                for point in coverage_points
            ]

        inferred_missing = [
            item["point"]
            for item in normalized_coverage
            if item["point"]
            and (
                item["support_count"] <= 0
                or item["status"].lower() in {"missing", "weak", "insufficient"}
            )
        ]
        if not missing_points:
            missing_points = inferred_missing
        sufficient = sufficient and not inferred_missing

        return {
            "sufficient": sufficient,
            "missing_points": [
                str(item).strip() for item in missing_points if str(item).strip()
            ],
            "follow_up_queries": [
                str(item).strip()
                for item in follow_up_queries[: self.MAX_FOLLOW_UP_QUERIES]
                if str(item).strip()
            ],
            "reasoning": str(parsed.get("reasoning", "")).strip()
            or "Fallback critique: coverage could not be fully assessed.",
            "coverage_matrix": normalized_coverage,
        }

    def _rewrite_section(
        self,
        user_request: str,
        section: TemplateSection,
        research_results: List[Dict[str, str]],
        evidence_records: List[EvidenceRecord],
        critique: CritiqueResult,
        writer_mode: str,
    ) -> str:
        evidence_snapshot = [
            {
                "fact": record.get("facts", ""),
                "primary_url": record.get("primary_url", ""),
                "source_urls": record.get("source_urls", [])[:3],
            }
            for record in evidence_records[:20]
        ]
        rewrite_prompt = (
            "You are rewriting ONE markdown section in a financial research outline.\n"
            "Use only the collected research. Preserve the section heading exactly.\n"
            "Preserve the section's internal outline shape as much as possible.\n"
            "Replace generic guidance with data-backed bullets or short paragraphs.\n"
            "If some outline points still lack data, keep them and note briefly that evidence is insufficient.\n"
            "Prefer the structured evidence ledger over any high-level summary.\n"
            "Return markdown for this section only.\n\n"
            f"User topic:\n{user_request}\n\n"
            f"Section heading:\n{section['heading_line']}\n\n"
            f"Writer mode recommendation:\n{writer_mode}\n\n"
            f"Original section body:\n{section['body']}\n\n"
            f"Critique:\n{json.dumps(critique, ensure_ascii=False, indent=2)}\n\n"
            f"Research results:\n{json.dumps(research_results, ensure_ascii=False, indent=2)}\n\n"
            f"Structured evidence ledger:\n{json.dumps(evidence_snapshot, ensure_ascii=False, indent=2)}"
        )

        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=rewrite_prompt),
                    HumanMessage(content="Rewrite the section now."),
                ]
            )
            rewritten = self._extract_text(response.content).strip()
        except Exception as exc:
            logger.warning(f"Section rewrite failed for {section['section_id']}: {exc}")
            rewritten = ""

        if not rewritten:
            fallback_lines = [section["heading_line"]]
            if section["body"]:
                fallback_lines.append(section["body"])
            fallback_lines.append("")
            fallback_lines.append(
                "_Data coverage is currently insufficient to rewrite this section confidently._"
            )
            return "\n".join(fallback_lines).strip()

        if not rewritten.startswith(section["heading_line"]):
            rewritten = f"{section['heading_line']}\n\n{rewritten}"
        return rewritten.strip()

    def _run_section_workflow(
        self, user_request: str, section: TemplateSection
    ) -> SectionWorkflowResult:
        plan = self._plan_section_queries(user_request, section, prefix="task")
        research_results = self._run_tasks_parallel(plan)
        evidence_records = self._load_section_evidence_records(section["section_id"])
        critique = self._critique_section_coverage(
            user_request, section, research_results, evidence_records
        )

        if not critique["sufficient"]:
            follow_up_tasks: List[ResearchTask] = []
            if critique["follow_up_queries"]:
                for idx, query in enumerate(critique["follow_up_queries"], start=1):
                    follow_up_tasks.append(
                        {
                            "task_id": f"{section['section_id']}_followup_{idx}",
                            "section_id": section["section_id"],
                            "section_title": section["section_title"],
                            "subquery": query,
                            "tool_hint": "mixed",
                            "rationale": "gap filling from critique",
                        }
                    )
            elif critique["missing_points"]:
                follow_up_tasks = self._plan_section_queries(
                    user_request,
                    section,
                    prefix="followup",
                    missing_points=critique["missing_points"],
                )

            if follow_up_tasks:
                research_results.extend(self._run_tasks_parallel(follow_up_tasks))
                research_results.sort(key=lambda item: item.get("task_id", ""))
                evidence_records = self._load_section_evidence_records(
                    section["section_id"]
                )
                critique = self._critique_section_coverage(
                    user_request, section, research_results, evidence_records
                )

        writer_mode = self._infer_writer_mode(section)
        rewritten_section = self._rewrite_section(
            user_request=user_request,
            section=section,
            research_results=research_results,
            evidence_records=evidence_records,
            critique=critique,
            writer_mode=writer_mode,
        )

        return {
            "section_id": section["section_id"],
            "section_title": section["section_title"],
            "plan": plan,
            "research_results": research_results,
            "critique": critique,
            "evidence_records": evidence_records,
            "writer_mode": writer_mode,
            "rewritten_section": rewritten_section,
        }

    def _planner_node(self, state: BuildState) -> Dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            raise ValueError("Build phase requires an initial user message.")

        user_message = messages[-1]
        user_content = (
            user_message.get("content", "")
            if isinstance(user_message, dict)
            else self._extract_text(getattr(user_message, "content", ""))
        )
        user_request, template_outline = self._extract_user_request_and_template(
            user_content
        )
        template_prefix = self._extract_template_prefix(template_outline)
        template_sections = self._split_template_sections(template_outline)
        parallel_sections = [
            section for section in template_sections if section["is_parallel_section"]
        ]

        plan_markdown = ["# Section Workflows", ""]
        for section in parallel_sections:
            plan_markdown.append(
                f"- `{section['section_id']}` | {section['section_title']}"
            )
        self._write_workspace_file("research_plan.md", "\n".join(plan_markdown) + "\n")

        logger.info(
            f"Planner identified {len(parallel_sections)} parallel section workflow(s)"
        )
        return {
            "user_request": user_request,
            "template_outline": template_outline,
            "template_prefix": template_prefix,
            "template_sections": template_sections,
            "parallel_sections": parallel_sections,
        }

    def _research_node(self, state: BuildState) -> Dict[str, Any]:
        parallel_sections = state.get("parallel_sections", [])
        user_request = state.get("user_request", "")
        if not parallel_sections:
            return {"section_results": []}

        section_results: List[SectionWorkflowResult] = []
        with ThreadPoolExecutor(max_workers=max(1, len(parallel_sections))) as executor:
            futures = {
                executor.submit(
                    self._run_section_workflow, user_request, section
                ): section
                for section in parallel_sections
            }
            for future in as_completed(futures):
                section_results.append(future.result())

        order_map = {
            section["section_id"]: idx for idx, section in enumerate(parallel_sections)
        }
        section_results.sort(
            key=lambda item: order_map.get(item.get("section_id", ""), 999)
        )

        summary_lines = ["# Section Research Results", ""]
        for section_result in section_results:
            critique = section_result["critique"]
            summary_lines.append(
                f"- `{section_result['section_id']}` | {section_result['section_title']} | sufficient={critique['sufficient']}"
            )
            summary_lines.append(f"  Critique: {critique['reasoning']}")
            summary_lines.append(
                f"  Evidence records: {len(section_result.get('evidence_records', []))} | writer_mode={section_result.get('writer_mode', 'direct')}"
            )
            for task in section_result["research_results"]:
                summary_lines.append(
                    f"  - `{task['task_id']}` | {task['status']} | {task['subquery']}"
                )
        self._write_workspace_file(
            "research_results.md", "\n".join(summary_lines) + "\n"
        )

        return {"section_results": section_results}

    def _build_title_section(
        self,
        user_request: str,
        title_section: Optional[TemplateSection],
        section_results: List[SectionWorkflowResult],
    ) -> str:
        if title_section is None:
            return ""

        title_prompt = (
            "You are generating the title section for a financial research outline.\n"
            "Preserve the heading exactly and replace the placeholder guidance with a concrete title/subtitle.\n"
            "Use the combined section findings to make the title specific.\n"
            "Return markdown for this section only.\n\n"
            f"User topic:\n{user_request}\n\n"
            f"Original title section:\n{title_section['heading_line']}\n\n{title_section['body']}\n\n"
            f"Section findings:\n{json.dumps(section_results, ensure_ascii=False, indent=2)}"
        )

        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=title_prompt),
                    HumanMessage(content="Rewrite the title section now."),
                ]
            )
            rewritten = self._extract_text(response.content).strip()
        except Exception as exc:
            logger.warning(f"Title section rewrite failed: {exc}")
            rewritten = ""

        if not rewritten:
            return (
                f"{title_section['heading_line']}\n\n"
                "_Tiêu đề tổng quan sẽ được hoàn thiện khi có thêm dữ liệu hỗ trợ._"
            )
        if not rewritten.startswith(title_section["heading_line"]):
            rewritten = f"{title_section['heading_line']}\n\n{rewritten}"
        return rewritten.strip()

    def _outline_node(self, state: BuildState) -> Dict[str, Any]:
        template_sections = state.get("template_sections", [])
        template_prefix = state.get("template_prefix", "")
        section_results = state.get("section_results", [])
        user_request = state.get("user_request", "")

        section_map = {
            result["section_id"]: result["rewritten_section"]
            for result in section_results
        }
        title_section = next(
            (
                section
                for section in template_sections
                if not section.get("is_parallel_section", False)
            ),
            None,
        )
        title_markdown = self._build_title_section(
            user_request, title_section, section_results
        )

        blocks: List[str] = []
        for section in template_sections:
            if not section["is_parallel_section"]:
                if title_markdown:
                    blocks.append(title_markdown)
                continue
            blocks.append(
                section_map.get(
                    section["section_id"],
                    f"{section['heading_line']}\n\n{section['body']}".strip(),
                )
            )

        all_blocks: List[str] = []
        if template_prefix.strip():
            all_blocks.append(template_prefix.strip())
        all_blocks.extend(block.strip() for block in blocks if block.strip())

        outline = "\n\n".join(all_blocks).strip()
        self._write_workspace_file("outline.md", outline + "\n")

        combined_payload = ["# Combined Section Outputs", ""]
        for section_result in section_results:
            combined_payload.append(section_result["rewritten_section"])
            combined_payload.append("")
        self._write_workspace_file(
            "combined_sections.md", "\n".join(combined_payload).strip() + "\n"
        )

        section_evidence_map = {
            "sections": [
                {
                    "section_id": result["section_id"],
                    "section_title": result["section_title"],
                    "heading_line": next(
                        (
                            section["heading_line"]
                            for section in template_sections
                            if section["section_id"] == result["section_id"]
                        ),
                        "",
                    ),
                    "writer_mode": result.get("writer_mode", "direct"),
                    "plan": result.get("plan", []),
                    "coverage_matrix": result.get("critique", {}).get(
                        "coverage_matrix", []
                    ),
                    "evidence_records": result.get("evidence_records", []),
                }
                for result in section_results
            ]
        }
        self._write_workspace_file(
            "section_evidence_map.json",
            json.dumps(section_evidence_map, ensure_ascii=False, indent=2) + "\n",
        )

        return {
            "outline": outline,
            "messages": [AIMessage(content=outline)],
        }

    def create(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph is required for the build phase but is not installed. "
                "Add the `langgraph` package to the environment before running phase=build."
            ) from exc

        self._get_workspace_path()
        set_current_session_id(self.session_id)
        clear_pending_graph_updates()

        graph = StateGraph(BuildState)
        graph.add_node("planner", self._planner_node)
        graph.add_node("research", self._research_node)
        graph.add_node("outline", self._outline_node)

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "research")
        graph.add_edge("research", "outline")
        graph.add_edge("outline", END)

        self._agent = LangGraphBuildAgent(
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


def create_builder_orchestrator(
    model: BaseChatModel,
    session_id: Optional[str] = None,
    output_base_path: str = "outputs",
) -> BuilderOrchestrator:
    orchestrator = BuilderOrchestrator(
        model=model,
        session_id=session_id,
        output_base_path=output_base_path,
    )
    return orchestrator
