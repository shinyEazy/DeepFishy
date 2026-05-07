import type {
  ProgressEvent,
  ResearchActivity,
  ReportPhase,
  ReportRequest,
  ReportResponse,
  ReportStatusResponse,
  ReportStreamEvent,
} from "@/features/report/types"
import type { ReportReference } from "@/features/report/lib/report-markdown"

async function assertOk(response: Response) {
  if (response.ok) {
    return
  }

  const errorText = await response.text()
  let message = errorText || `Request failed with status ${response.status}`
  try {
    const parsed = JSON.parse(errorText)
    if (parsed.detail) message = parsed.detail
    else if (parsed.error?.message) message = parsed.error.message
    else if (parsed.message) message = parsed.message
  } catch {}

  const error = new Error(message) as Error & { status?: number }
  error.status = response.status
  throw error
}

export async function generateReport(
  request: ReportRequest
): Promise<ReportResponse> {
  const response = await fetch("/api/reports/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      topic: request.topic,
      phase: request.phase ?? null,
      session_id: request.session_id ?? null,
      conversation_id: request.conversation_id ?? null,
      use_knowledge_graph: request.use_knowledge_graph ?? true,
      stream: false,
      classify_only: request.classify_only ?? false,
      model_name: request.model_name,
    }),
  })

  await assertOk(response)
  return (await response.json()) as ReportResponse
}

export async function streamReportGeneration(
  request: ReportRequest,
  handlers: {
    onStarted?: (
      sessionId: string,
      phases: ReportPhase[],
      conversationId?: string
    ) => void
    onProgress?: (event: ProgressEvent, activity?: ResearchActivity) => void
    onCompleted?: (
      sessionId: string,
      outputFiles: string[],
      message: string,
      conversationId?: string
    ) => void
    onError?: (
      sessionId: string,
      error: string,
      message: string,
      conversationId?: string
    ) => void
    onDisconnected?: (sessionId: string) => void
  }
) {
  const response = await fetch("/api/reports/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      topic: request.topic,
      phase: request.phase ?? null,
      session_id: request.session_id ?? null,
      conversation_id: request.conversation_id ?? null,
      use_knowledge_graph: request.use_knowledge_graph ?? true,
      stream: true,
      model_name: request.model_name,
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    let message = errorText || `Request failed with status ${response.status}`
    try {
      const parsed = JSON.parse(errorText)
      if (parsed.detail) message = parsed.detail
    } catch {}
    throw new Error(message)
  }

  if (!response.body) {
    throw new Error("Streaming response body is not available.")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let startedSessionId: string | null = null

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      const events = buffer.split("\n\n")
      buffer = events.pop() ?? ""

      for (const event of events) {
        const line = event
          .split("\n")
          .find((part) => part.trimStart().startsWith("data:"))

        if (!line) {
          continue
        }

        const payload = line.replace(/^data:\s*/, "")
        const parsed = JSON.parse(payload) as ReportStreamEvent

        if (parsed.type === "started") {
          startedSessionId = parsed.session_id
          handlers.onStarted?.(
            parsed.session_id,
            parsed.phases,
            parsed.conversation_id
          )
          continue
        }

        if (parsed.type === "heartbeat") {
          startedSessionId = parsed.session_id
          continue
        }

        if (parsed.type === "progress") {
          handlers.onProgress?.(parsed.data, parsed.activity)
          continue
        }

        if (parsed.type === "completed") {
          handlers.onCompleted?.(
            parsed.session_id,
            parsed.output_files,
            parsed.message,
            parsed.conversation_id
          )
          return
        }

        if (parsed.type === "error") {
          handlers.onError?.(
            parsed.session_id,
            parsed.error,
            parsed.message,
            parsed.conversation_id
          )
          return
        }
      }

      if (done) {
        if (startedSessionId) {
          handlers.onDisconnected?.(startedSessionId)
        }
        return
      }
    }
  } catch (error) {
    if (startedSessionId) {
      handlers.onDisconnected?.(startedSessionId)
      return
    }
    throw error
  }
}

export async function getReportStatus(
  sessionId: string
): Promise<ReportStatusResponse> {
  const response = await fetch(
    `/api/reports/${encodeURIComponent(sessionId)}`,
    {
      cache: "no-store",
    }
  )

  await assertOk(response)
  return (await response.json()) as ReportStatusResponse
}

export async function getReportContent(
  sessionId: string
): Promise<{
  session_id: string
  content: string
  format: string
  unused_references?: ReportReference[]
}> {
  const response = await fetch(
    `/api/reports/${encodeURIComponent(sessionId)}/content`,
    { cache: "no-store" }
  )

  await assertOk(response)
  return await response.json()
}
