import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from engine.orchestrators.classifier import classify_topic

from deepfishy.features.chat.response_service import ResponseService
from deepfishy.features.reports.application.generate_report import create_model
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.models.conversation import Message

from deepfishy.app.api.deps import get_db
from deepfishy.features.chat.service import ChatService
from deepfishy.shared.logging import logger

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORT_STATES: dict[str, dict] = {}


def _initial_report_state(phases: list[str]) -> dict[str, Any]:
    return {
        "status": "in_progress",
        "phases_completed": [],
        "output_files": [],
        "current_phase": phases[0] if phases else None,
        "current_stage": "classify",
        "message": "Đang phân loại chủ đề...",
        "created_at": datetime.now().isoformat(),
        "activities": [],
        "activity_sequence": 0,
        "updated_at": int(time.time() * 1000),
    }


def _normalize_progress_activity(
    session_id: str,
    event_data: dict[str, Any],
    sequence: int,
) -> dict[str, Any]:
    activity_type = event_data.get("type") or event_data.get("stage") or "info"
    activity = {
        "id": f"{session_id}-{sequence}",
        "type": activity_type,
        "message": event_data.get("message") or "",
        "timestamp": int(time.time() * 1000),
        "stage": event_data.get("stage"),
        "phase": event_data.get("phase"),
        "query": event_data.get("query"),
        "results": event_data.get("results"),
        "result_count": event_data.get("result_count"),
        "ticker": event_data.get("ticker"),
        "count": event_data.get("count"),
        "section": event_data.get("section"),
        "filename": event_data.get("filename"),
    }
    return {key: value for key, value in activity.items() if value is not None}


def _report_thinking_metadata(session_id: str) -> dict[str, Any]:
    activities = REPORT_STATES.get(session_id, {}).get("activities", [])
    return {
        "thinking_process": activities,
        "activity_count": len(activities),
    }


def _persisted_report_history(
    session_id: str, db: Session | None = None
) -> dict[str, Any]:
    if db is None:
        return {"activities": [], "activity_count": 0}

    messages = (
        db.query(Message)
        .filter(Message.role == "assistant")
        .order_by(desc(Message.created_at))
        .limit(200)
        .all()
    )
    message = next(
        (
            item
            for item in messages
            if isinstance(item.meta, dict)
            and item.meta.get("report_session_id") == session_id
        ),
        None,
    )

    metadata = message.meta if message and isinstance(message.meta, dict) else {}
    activities = metadata.get("thinking_process")
    if not isinstance(activities, list):
        activities = []

    activity_count = metadata.get("activity_count")
    if not isinstance(activity_count, int):
        activity_count = len(activities)

    return {
        "activities": activities,
        "activity_count": activity_count,
        "report_status": metadata.get("report_status"),
        "phases": metadata.get("phases"),
        "message": message.content if message else None,
    }


class ReportRequest(BaseModel):
    """Request schema for report generation."""

    topic: str = Field(
        ...,
        min_length=1,
        description="Report topic",
    )
    phase: Optional[str] = Field(
        default=None,
        description="Phase to run: 'build', 'write', or null for both",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID to reuse existing workspace",
    )
    use_knowledge_graph: bool = Field(
        default=True,
        description="Whether to use knowledge graph in generation",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream progress updates via SSE",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional chat conversation ID for persisting the deep research transcript",
    )
    classify_only: bool = Field(
        default=False,
        description="Whether to classify the topic first and return plan-or-answer guidance without starting generation",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Optional configured LLM model name for report generation",
    )


class ReportResponse(BaseModel):
    """Response schema for report generation."""

    session_id: str
    status: str
    topic: str
    phases: list[str]
    message: str
    action: Optional[str] = None
    conversation_id: Optional[str] = None


class ReportStatusResponse(BaseModel):
    """Response schema for report status."""

    session_id: str
    status: str
    phases_completed: list[str]
    output_files: list[str]
    created_at: Optional[str] = None
    current_phase: Optional[str] = None
    current_stage: Optional[str] = None
    message: Optional[str] = None
    activities: list[dict[str, Any]] = Field(default_factory=list)
    activity_count: int = 0
    updated_at: Optional[int] = None


class ProgressCallback:
    """Callback to send progress events via SSE."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()

    async def emit(self, event_type: str, data: dict):
        """Emit a progress event."""
        await self.queue.put(
            {
                "type": event_type,
                "data": data,
            }
        )


def _run_report_generation_with_progress(
    topic: str,
    session_id: str,
    phases: list[str],
    use_knowledge_graph: bool,
    callback_queue: asyncio.Queue,
    model_name: str | None = None,
) -> dict:
    """Run report generation synchronously with progress callbacks."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    _asyncio.set_event_loop(loop)

    try:
        from deepfishy.features.reports.application.generate_report import (
            DEFAULT_TOPIC,
            run_engine,
        )
        from deepfishy.features.reports.application.generate_dataset_reports import (
            format_user_input,
        )

        user_input = format_user_input(topic or DEFAULT_TOPIC)

        # Create a custom logging handler that emits events
        import logging

        class ProgressHandler(logging.Handler):
            def emit(self, record):
                msg = record.getMessage()
                progress_data = getattr(record, "progress_data", None) or {}

                # Parse log messages and emit progress events
                event_data = None

                if "Classifying topic" in msg:
                    event_data = {
                        "stage": "classify",
                        "phase": "build",
                        "message": "Đang phân loại chủ đề...",
                    }
                elif (
                    "PHASE 1: Build" in msg
                    or "Creating Builder Orchestrator" in msg
                    or "Starting agent invocation for phase build" in msg
                    or "Cleared existing graph data" in msg
                    or "Cleared knowledge graph" in msg
                    or "Topic unknown" in msg
                    or "Falling back to default outline" in msg
                ):
                    event_data = {
                        "stage": "build",
                        "phase": "build",
                        "message": "Đang tổng hợp dữ liệu nghiên cứu...",
                    }
                elif "PHASE 2: Write" in msg:
                    event_data = {
                        "stage": "write",
                        "phase": "write",
                        "message": "Bắt đầu soạn báo cáo...",
                    }
                elif "identified" in msg and "section workflow" in msg:
                    event_data = {
                        "stage": "plan",
                        "phase": "build",
                        "message": "Đã xác định 1 luồng nghiên cứu cho báo cáo",
                    }
                elif "Web search:" in msg:
                    query = (
                        msg.split("Web search: '")[1].split("'")[0]
                        if "'" in msg
                        else ""
                    )
                    result_count = (
                        msg.split("→ ")[1].split(" results")[0] if "→ " in msg else "0"
                    )
                    event_data = {
                        "stage": "research",
                        "type": "web",
                        "query": progress_data.get("query") or query,
                        "results": progress_data.get("results", []),
                        "result_count": (
                            int(result_count) if result_count.isdigit() else 0
                        ),
                        "message": f"🔍 Web: {query[:50]}... → {result_count} kết quả",
                    }
                elif "Local search:" in msg:
                    query = (
                        msg.split("Local search: '")[1].split("'")[0]
                        if "'" in msg
                        else ""
                    )
                    results = (
                        msg.split("→ ")[1].split(" results")[0] if "→ " in msg else "0"
                    )
                    event_data = {
                        "stage": "research",
                        "type": "local",
                        "query": query,
                        "results": int(results) if results.isdigit() else 0,
                        "message": f"📚 Local: {query[:50]}... → {results} kết quả",
                    }
                elif "Finance API: fetching" in msg:
                    ticker = (
                        msg.split("fetching ")[1].split(" from")[0]
                        if "fetching " in msg
                        else ""
                    )
                    event_data = {
                        "stage": "research",
                        "type": "finance",
                        "ticker": ticker,
                        "message": f"Đang phân tích dữ liệu tài chính {ticker}",
                    }
                elif "commit_facts_to_graph:" in msg and "staged" in msg:
                    facts = (
                        msg.split("staged ")[1].split(" facts")[0]
                        if "staged " in msg
                        else "0"
                    )
                    section = (
                        msg.split("section=")[1].split(" ")[0]
                        if "section=" in msg
                        else ""
                    )
                    section_label = (
                        section.replace("section_", "phần ")
                        if section
                        else "mục hiện tại"
                    )
                    event_data = {
                        "stage": "facts",
                        "count": int(facts) if facts.isdigit() else 0,
                        "section": section,
                        "message": f"Đã tổng hợp {facts} bằng chứng cho {section_label}",
                    }
                elif "Builder wrote" in msg:
                    filename = (
                        msg.split("wrote ")[1].split(" to")[0]
                        if "wrote " in msg
                        else ""
                    )
                    filename_labels = {
                        "research_results.md": "bản tổng hợp kết quả nghiên cứu",
                        "research_plan.md": "kế hoạch nghiên cứu",
                        "outline.md": "dàn ý báo cáo",
                        "combined_sections.md": "các phần nội dung tổng hợp",
                        "section_evidence_map.json": "liên kết bằng chứng với từng phần",
                    }
                    label = filename_labels.get(filename, filename)
                    event_data = {
                        "stage": "output",
                        "filename": filename,
                        "message": f"Đã tạo {label}",
                    }
                elif "TOTAL BUILD PHASE" in msg:
                    event_data = {
                        "stage": "build_complete",
                        "phase": "build",
                        "message": "Hoàn tất tổng hợp dữ liệu",
                    }
                elif "Creating Report Writer" in msg:
                    event_data = {
                        "stage": "write_start",
                        "phase": "write",
                        "message": "Đang chuẩn bị trình soạn báo cáo...",
                    }

                if event_data:
                    state = REPORT_STATES.setdefault(
                        session_id, _initial_report_state(phases)
                    )
                    state["activity_sequence"] = state.get("activity_sequence", 0) + 1
                    activity = _normalize_progress_activity(
                        session_id,
                        event_data,
                        state["activity_sequence"],
                    )
                    state.setdefault("activities", []).append(activity)
                    state["updated_at"] = activity["timestamp"]
                    state["status"] = "in_progress"
                    state["current_stage"] = event_data.get("stage")
                    state["message"] = event_data.get("message")
                    if event_data.get("phase"):
                        state["current_phase"] = event_data["phase"]
                    if (
                        event_data.get("stage") == "build_complete"
                        and "build" not in state["phases_completed"]
                    ):
                        state["phases_completed"].append("build")
                        state["current_phase"] = "write" if "write" in phases else None
                    if event_data.get("stage") in ("write", "write_start"):
                        if (
                            "build" in phases
                            and "build" not in state["phases_completed"]
                        ):
                            state["phases_completed"].append("build")
                        state["current_phase"] = "write"

                    try:
                        loop.call_soon_threadsafe(
                            callback_queue.put_nowait,
                            {
                                "type": "progress",
                                "data": event_data,
                                "activity": activity,
                            },
                        )
                    except Exception:
                        pass

        # Add progress handler to deepfishy logger
        progress_handler = ProgressHandler()
        progress_handler.setLevel(logging.INFO)

        from deepfishy.shared.logging import logger as deepfishy_logger

        deepfishy_logger.addHandler(progress_handler)

        try:
            run_engine(
                user_input=user_input,
                session_id=session_id,
                phases=phases,
                model_name=model_name,
            )
        finally:
            deepfishy_logger.removeHandler(progress_handler)

        # Check output files
        from deepfishy.infra.config.paths import OUTPUTS_DIR

        workspace_path = OUTPUTS_DIR / session_id
        output_files = []
        if workspace_path.exists():
            for f in workspace_path.rglob("*"):
                if f.is_file():
                    output_files.append(str(f.relative_to(workspace_path)))

        REPORT_STATES[session_id] = {
            **REPORT_STATES.get(session_id, {}),
            "status": "completed",
            "phases_completed": phases,
            "output_files": output_files,
            "current_phase": None,
            "current_stage": None,
            "message": f"Report generation completed for topic: {topic}",
            "updated_at": int(time.time() * 1000),
        }

        return {
            "success": True,
            "session_id": session_id,
            "output_files": output_files,
            "message": f"Report generation completed for topic: {topic}",
        }
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        REPORT_STATES[session_id] = {
            **REPORT_STATES.get(session_id, {}),
            "status": "failed",
            "current_phase": None,
            "current_stage": None,
            "message": f"Report generation failed: {str(e)}",
            "updated_at": int(time.time() * 1000),
        }

        return {
            "success": False,
            "session_id": session_id,
            "error": str(e),
            "message": f"Report generation failed: {str(e)}",
        }
    finally:
        loop.close()


@router.post("/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest, db: Session = Depends(get_db)):
    """Generate a financial research report."""
    session_id = request.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    phases = [request.phase] if request.phase else ["build", "write"]
    chat_service = ChatService(db)
    conversation = chat_service.get_or_create_conversation(request.conversation_id)
    chat_service.ensure_conversation_title(conversation, request.topic)

    if request.classify_only:
        chat_service.save_message(
            conversation_id=conversation.id,
            role="user",
            content=request.topic,
            metadata={
                "source": "reports_api",
                "mode": "deep",
                "classification_only": True,
            },
        )

        model = create_model(request.model_name)
        topic_type = classify_topic(model, request.topic)

        if topic_type in {1, 2}:
            return ReportResponse(
                session_id=session_id,
                status="idle",
                topic=request.topic,
                phases=phases,
                message="Đây là kế hoạch tôi đã chuẩn bị. Nếu bạn cần chỉnh sửa gì, hãy cho tôi biết trước khi tôi bắt đầu nghiên cứu.",
                action="plan",
                conversation_id=conversation.id,
            )

        response_service = ResponseService(model_name=request.model_name)
        system_instruction = (
            "Answer conversationally in the user's language. "
            "Explain that deep research needs a clearer research target, ask what they want to search about, "
            "and give a few examples such as a company, an industry/sector, or a macroeconomic topic. "
            "If the message is a greeting or casual chat, respond naturally and invite them to provide a research topic when ready."
        )
        contents = [
            {"role": "system", "parts": [{"text": system_instruction}]},
            {"role": "user", "parts": [{"text": request.topic}]},
        ]
        answer = response_service.generate_response(contents)
        chat_service.save_message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            metadata={
                "source": "reports_api",
                "mode": "deep",
                "classification_only": True,
                "classification_result": "answer",
                "model_name": response_service.model_name,
            },
        )
        return ReportResponse(
            session_id=session_id,
            status="completed",
            topic=request.topic,
            phases=phases,
            message=answer,
            action="answer",
            conversation_id=conversation.id,
        )

    chat_service.save_message(
        conversation_id=conversation.id,
        role="user",
        content=request.topic,
        metadata={"source": "reports_api", "mode": "deep"},
    )
    REPORT_STATES[session_id] = _initial_report_state(phases)

    if request.stream:
        callback_queue: asyncio.Queue = asyncio.Queue()

        async def event_stream():
            # Send started event
            yield f"data: {json.dumps({'type': 'started', 'session_id': session_id, 'conversation_id': conversation.id, 'phases': phases})}\n\n"
            last_heartbeat = asyncio.get_event_loop().time()

            # Start generation in background thread
            loop = asyncio.get_event_loop()
            gen_task = loop.run_in_executor(
                None,
                _run_report_generation_with_progress,
                request.topic,
                session_id,
                phases,
                request.use_knowledge_graph,
                callback_queue,
                request.model_name,
            )

            # Forward events from queue
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(callback_queue.get(), timeout=0.5)
                    yield f"data: {json.dumps(event)}\n\n"

                    # Check if this is a terminal event
                    if event.get("type") in ("completed", "error"):
                        break
                except asyncio.TimeoutError:
                    # Keep the SSE/proxy connection alive during long LLM/Graphiti calls.
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= 10:
                        last_heartbeat = now
                        yield f"data: {json.dumps({'type': 'heartbeat', 'session_id': session_id})}\n\n"

                    # Check if generation is done
                    if gen_task.done():
                        # Get result
                        result = gen_task.result()

                        # Send final event
                        if result["success"]:
                            chat_service.save_message(
                                conversation_id=conversation.id,
                                role="assistant",
                                content=result["message"],
                                metadata={
                                    "source": "reports_api",
                                    "mode": "deep",
                                    "report_session_id": session_id,
                                    "report_status": "completed",
                                    "topic": request.topic,
                                    "phases": phases,
                                    "model_name": request.model_name,
                                    **_report_thinking_metadata(session_id),
                                },
                            )
                            yield f"data: {json.dumps({'type': 'completed', 'session_id': session_id, 'conversation_id': conversation.id, 'output_files': result['output_files'], 'message': result['message']})}\n\n"
                        else:
                            chat_service.save_message(
                                conversation_id=conversation.id,
                                role="assistant",
                                content=result["message"],
                                metadata={
                                    "source": "reports_api",
                                    "mode": "deep",
                                    "report_session_id": session_id,
                                    "report_status": "failed",
                                    "topic": request.topic,
                                    "phases": phases,
                                    "error": result.get("error", "Unknown"),
                                    **_report_thinking_metadata(session_id),
                                },
                            )
                            yield f"data: {json.dumps({'type': 'error', 'session_id': session_id, 'conversation_id': conversation.id, 'error': result.get('error', 'Unknown'), 'message': result['message']})}\n\n"
                        break
                    continue

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming mode
    loop = asyncio.get_event_loop()
    callback_queue: asyncio.Queue = asyncio.Queue()
    result = await loop.run_in_executor(
        None,
        _run_report_generation_with_progress,
        request.topic,
        session_id,
        phases,
        request.use_knowledge_graph,
        callback_queue,
        request.model_name,
    )

    if not result["success"]:
        chat_service.save_message(
            conversation_id=conversation.id,
            role="assistant",
            content=result["message"],
            metadata={
                "source": "reports_api",
                "mode": "deep",
                "report_session_id": session_id,
                "report_status": "failed",
                "topic": request.topic,
                "phases": phases,
                "error": result.get("error", "Unknown"),
                **_report_thinking_metadata(session_id),
            },
        )
        raise HTTPException(status_code=500, detail=result["message"])

    chat_service.save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["message"],
        metadata={
            "source": "reports_api",
            "mode": "deep",
            "report_session_id": session_id,
            "report_status": "completed",
            "topic": request.topic,
            "phases": phases,
            **_report_thinking_metadata(session_id),
        },
    )

    return ReportResponse(
        session_id=session_id,
        status="completed",
        topic=request.topic,
        phases=phases,
        message=result["message"],
    )


@router.get("/{session_id}/status", response_model=ReportStatusResponse)
async def get_report_status(session_id: str, db: Session = Depends(get_db)):
    """Get the status of a report generation."""
    from deepfishy.infra.config.paths import OUTPUTS_DIR

    workspace_path = OUTPUTS_DIR / session_id
    live_state = REPORT_STATES.get(session_id, {})
    persisted = _persisted_report_history(session_id, db)

    if not workspace_path.exists() and not live_state and not persisted["activities"]:
        raise HTTPException(status_code=404, detail="Report session not found")

    output_files = []
    if workspace_path.exists():
        for f in workspace_path.rglob("*"):
            if f.is_file():
                output_files.append(str(f.relative_to(workspace_path)))

    has_final_md = any("final.md" in f for f in output_files)
    file_phases_completed = []
    if any("outline.md" in f for f in output_files):
        file_phases_completed.append("build")
    if has_final_md:
        file_phases_completed.append("write")

    persisted_status = persisted.get("report_status")
    status = (
        "completed"
        if has_final_md
        else live_state.get("status")
        or (
            persisted_status
            if persisted_status in {"completed", "failed"}
            else "in_progress"
        )
    )
    phases_completed = live_state.get("phases_completed") or file_phases_completed
    if has_final_md:
        phases_completed = ["build", "write"]
    elif not phases_completed and status == "completed":
        phases = persisted.get("phases")
        if isinstance(phases, list):
            phases_completed = [
                phase for phase in phases if phase in {"build", "write"}
            ]

    activities = live_state.get("activities") or persisted["activities"]
    activity_count = (
        len(activities) if live_state.get("activities") else persisted["activity_count"]
    )

    return ReportStatusResponse(
        session_id=session_id,
        status=status,
        phases_completed=phases_completed,
        output_files=output_files,
        created_at=live_state.get("created_at"),
        current_phase=(
            None if has_final_md or not live_state else live_state.get("current_phase")
        ),
        current_stage=(
            None if has_final_md or not live_state else live_state.get("current_stage")
        ),
        message=live_state.get("message") or persisted.get("message"),
        activities=activities,
        activity_count=activity_count,
        updated_at=live_state.get("updated_at"),
    )


def _reference_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).hostname.replace("www.", "")
    except Exception:
        return url


def _normalize_reference_url(url: str) -> str:
    return url.strip().rstrip("),.;]")


def _extract_reference_candidates(markdown: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for match in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", markdown):
        url = _normalize_reference_url(match.group(2))
        title = match.group(1).strip() or _reference_domain(url)
        references.append({"title": title, "url": url, "domain": _reference_domain(url)})

    for match in re.finditer(r"https?://\S+", markdown):
        url = _normalize_reference_url(match.group(0))
        if any(item["url"] == url for item in references):
            continue
        line_start = markdown.rfind("\n", 0, match.start()) + 1
        line_end = markdown.find("\n", match.end())
        line = markdown[line_start : line_end if line_end != -1 else len(markdown)]
        title = line.replace(match.group(0), "").strip(" -:[]0123456789")
        domain = _reference_domain(url)
        references.append({"title": title or domain, "url": url, "domain": domain})

    return references


def _dedupe_references(references: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: dict[str, dict[str, str]] = {}
    for reference in references:
        url = reference["url"]
        if url not in deduped:
            deduped[url] = reference
    return list(deduped.values())


def _final_reference_block(markdown: str) -> str:
    matches = list(re.finditer(r"(^|\n)(#{1,6}\s*)?References\s*\n", markdown, re.IGNORECASE))
    if not matches:
        return markdown
    match = matches[-1]
    return markdown[match.end() :].strip()


def _unused_writer_references(workspace_path) -> list[dict[str, str]]:
    final_md_path = workspace_path / "final.md"
    final_content = final_md_path.read_text(encoding="utf-8")
    used_urls = {
        reference["url"]
        for reference in _extract_reference_candidates(_final_reference_block(final_content))
    }
    used_urls.update(
        reference["url"] for reference in _extract_reference_candidates(final_content)
    )

    writer_references: list[dict[str, str]] = []
    for evidence_path in sorted(workspace_path.glob("section_*/evidence.md")):
        writer_references.extend(
            _extract_reference_candidates(evidence_path.read_text(encoding="utf-8"))
        )

    unused = [
        reference
        for reference in _dedupe_references(writer_references)
        if reference["url"] not in used_urls
    ]

    return [
        {"id": f"u{index}", **reference}
        for index, reference in enumerate(unused, start=1)
    ]


@router.get("/{session_id}/content")
async def get_report_content(session_id: str):
    """Get the markdown content of a generated report."""
    from deepfishy.infra.config.paths import OUTPUTS_DIR

    workspace_path = OUTPUTS_DIR / session_id
    final_md_path = workspace_path / "final.md"

    if not final_md_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    content = final_md_path.read_text(encoding="utf-8")
    return {
        "session_id": session_id,
        "content": content,
        "format": "markdown",
        "unused_references": _unused_writer_references(workspace_path),
    }


@router.get("/{session_id}/pdf")
async def get_report_pdf(session_id: str):
    from deepfishy.infra.config.paths import OUTPUTS_DIR

    final_pdf_path = OUTPUTS_DIR / session_id / "final.pdf"

    if not final_pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report PDF not found")

    return FileResponse(
        final_pdf_path,
        media_type="application/pdf",
        filename=f"report-{session_id}.pdf",
        headers={"Content-Disposition": "inline"},
    )


__all__ = ["router", "ReportRequest", "ReportResponse"]
