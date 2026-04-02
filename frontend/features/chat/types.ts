export type Mode = "deep" | "normal"

export type SessionSummary = {
  id: string
  title: string
  preview: string
  time: string
  status: string
  mode: Mode
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
  id: string
  title: string
  mode: Mode
  subtitle: string
  inputPlaceholder: string
  quickActions: readonly string[]
  transcript: readonly TranscriptMessage[]
}

export type ResponsePart = {
  text: string
}

export type ResponsesApiPayload = {
  role: string
  parts: ResponsePart[]
}
