export type Mode = "deep" | "normal"

export type SessionSummary = {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
}

export type SessionMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  createdAt: string
  metadata?: Record<string, unknown> | null
}

export type SessionDetail = {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: SessionMessage[]
}

export type TranscriptMessage = {
  role: "user" | "assistant"
  mode: Mode
  label: string
  title: string
  body: string
  meta: string
  bullets?: readonly string[]
  references?: readonly string[]
}

export type SessionContent = {
  id?: string
  title: string
  mode: Mode
  inputPlaceholder: string
  transcript: readonly TranscriptMessage[]
}
