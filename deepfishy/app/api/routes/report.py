import asyncio
import json
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


class ReportResponse(BaseModel):
    """Response schema for report generation."""

    session_id: str
    status: str
    topic: str
    phases: list[str]
    message: str


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
        await self.queue.put({
            "type": event_type,
            "data": data,
        })


def _run_report_generation_with_progress(
    topic: str,
    session_id: str,
    phases: list[str],
    use_knowledge_graph: bool,
    callback_queue: asyncio.Queue,
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
                    event_data = {"stage": "classify", "phase": "build", "message": "Đang phân loại chủ đề..."}
                elif (
                    "PHASE 1: Build" in msg
                    or "Creating Builder Orchestrator" in msg
                    or "Starting agent invocation for phase build" in msg
                    or "Cleared existing graph data" in msg
                    or "Cleared knowledge graph" in msg
                    or "Topic unknown" in msg
                    or "Falling back to default outline" in msg
                ):
                    event_data = {"stage": "build", "phase": "build", "message": "Bắt đầu xây dựng đồ thị tri thức..."}
                elif "PHASE 2: Write" in msg:
                    event_data = {"stage": "write", "phase": "write", "message": "Bắt đầu viết báo cáo..."}
                elif "identified" in msg and "section workflow" in msg:
                    event_data = {"stage": "plan", "phase": "build", "message": msg}
                elif "Web search:" in msg:
                    query = msg.split("Web search: '")[1].split("'")[0] if "'" in msg else ""
                    result_count = msg.split("→ ")[1].split(" results")[0] if "→ " in msg else "0"
                    event_data = {
                        "stage": "research",
                        "type": "web",
                        "query": progress_data.get("query") or query,
                        "results": progress_data.get("results", []),
                        "result_count": int(result_count) if result_count.isdigit() else 0,
                        "message": f"🔍 Web: {query[:50]}... → {result_count} kết quả",
                    }
                elif "Local search:" in msg:
                    query = msg.split("Local search: '")[1].split("'")[0] if "'" in msg else ""
                    results = msg.split("→ ")[1].split(" results")[0] if "→ " in msg else "0"
                    event_data = {
                        "stage": "research",
                        "type": "local",
                        "query": query,
                        "results": int(results) if results.isdigit() else 0,
                        "message": f"📚 Local: {query[:50]}... → {results} kết quả",
                    }
                elif "Finance API: fetching" in msg:
                    ticker = msg.split("fetching ")[1].split(" from")[0] if "fetching " in msg else ""
                    event_data = {"stage": "research", "type": "finance", "ticker": ticker, "message": f"📊 Finance: {ticker}"}
                elif "commit_facts_to_graph:" in msg and "staged" in msg:
                    facts = msg.split("staged ")[1].split(" facts")[0] if "staged " in msg else "0"
                    section = msg.split("section=")[1].split(" ")[0] if "section=" in msg else ""
                    event_data = {"stage": "facts", "count": int(facts) if facts.isdigit() else 0, "section": section, "message": f"✅ Staged {facts} facts for {section}"}
                elif "Builder wrote" in msg:
                    filename = msg.split("wrote ")[1].split(" to")[0] if "wrote " in msg else ""
                    event_data = {"stage": "output", "filename": filename, "message": f"📝 Tạo {filename}"}
                elif "TOTAL BUILD PHASE" in msg:
                    event_data = {"stage": "build_complete", "phase": "build", "message": msg}
                elif "Creating Report Writer" in msg:
                    event_data = {"stage": "write_start", "phase": "write", "message": "Khởi tạo Writer..."}

                if event_data:
                    state = REPORT_STATES.setdefault(session_id, _initial_report_state(phases))
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
                    if event_data.get("stage") == "build_complete" and "build" not in state["phases_completed"]:
                        state["phases_completed"].append("build")
                        state["current_phase"] = "write" if "write" in phases else None
                    if event_data.get("stage") in ("write", "write_start"):
                        if "build" in phases and "build" not in state["phases_completed"]:
                            state["phases_completed"].append("build")
                        state["current_phase"] = "write"

                    try:
                        loop.call_soon_threadsafe(
                            callback_queue.put_nowait,
                            {"type": "progress", "data": event_data, "activity": activity}
                        )
                    except Exception:
                        pass

        # Add progress handler to deepfishy logger
        progress_handler = ProgressHandler()
        progress_handler.setLevel(logging.INFO)

        from deepfishy.shared.logging import logger as deepfishy_logger
        deepfishy_logger.addHandler(progress_handler)

        try:
            run_engine(user_input=user_input, session_id=session_id, phases=phases)
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
async def get_report_status(session_id: str):
    """Get the status of a report generation."""
    from deepfishy.infra.config.paths import OUTPUTS_DIR

    workspace_path = OUTPUTS_DIR / session_id
    live_state = REPORT_STATES.get(session_id, {})

    if not workspace_path.exists() and not live_state:
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

    status = "completed" if has_final_md else live_state.get("status", "in_progress")
    phases_completed = live_state.get("phases_completed") or file_phases_completed
    if has_final_md:
        phases_completed = ["build", "write"]

    activities = live_state.get("activities", [])

    return ReportStatusResponse(
        session_id=session_id,
        status=status,
        phases_completed=phases_completed,
        output_files=output_files,
        created_at=live_state.get("created_at"),
        current_phase=None if has_final_md else live_state.get("current_phase"),
        current_stage=None if has_final_md else live_state.get("current_stage"),
        message=live_state.get("message"),
        activities=activities,
        activity_count=len(activities),
        updated_at=live_state.get("updated_at"),
    )


@router.get("/{session_id}/content")
async def get_report_content(session_id: str):
    """Get the markdown content of a generated report."""
    from deepfishy.infra.config.paths import OUTPUTS_DIR

    workspace_path = OUTPUTS_DIR / session_id
    final_md_path = workspace_path / "final.md"

    if not final_md_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    content = final_md_path.read_text(encoding="utf-8")
    return {"session_id": session_id, "content": content, "format": "markdown"}


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
