import type {
  SessionDetail,
  SessionMessage,
  SessionSummary,
} from "@/features/chat/types"

type SessionSummaryApiPayload = {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

type SessionMessageApiPayload = {
  id: string
  role: "user" | "assistant"
  content: string
  created_at: string
  metadata?: Record<string, unknown> | null
}

type SessionDetailApiPayload = {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: SessionMessageApiPayload[]
}

type SessionListApiPayload = {
  sessions: SessionSummaryApiPayload[]
  total: number
  limit: number
  offset: number
}

function mapSessionSummary(session: SessionSummaryApiPayload): SessionSummary {
  return {
    id: session.id,
    title: session.title,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    messageCount: session.message_count,
  }
}

function mapSessionMessage(message: SessionMessageApiPayload): SessionMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    metadata: message.metadata ?? null,
  }
}

function mapSessionDetail(session: SessionDetailApiPayload): SessionDetail {
  return {
    id: session.id,
    title: session.title,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    messages: session.messages.map(mapSessionMessage),
  }
}

async function assertOk(response: Response) {
  if (response.ok) {
    return
  }

  const errorText = await response.text()
  const error = new Error(
    errorText || `Request failed with status ${response.status}`
  ) as Error & { status?: number }
  error.status = response.status
  throw error
}

export async function listSessions(limit = 100) {
  const response = await fetch(`/api/sessions?limit=${limit}`, {
    cache: "no-store",
  })
  await assertOk(response)

  const payload = (await response.json()) as SessionListApiPayload
  return {
    ...payload,
    sessions: payload.sessions.map(mapSessionSummary),
  }
}

export async function getSession(sessionId: string) {
  const response = await fetch(`/api/sessions/${sessionId}`, {
    cache: "no-store",
  })
  await assertOk(response)

  return mapSessionDetail((await response.json()) as SessionDetailApiPayload)
}

export async function createSession(title?: string) {
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(title ? { title } : {}),
  })
  await assertOk(response)

  return mapSessionDetail((await response.json()) as SessionDetailApiPayload)
}
