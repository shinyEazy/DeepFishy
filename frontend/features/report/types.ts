export type ReportPhase = "build" | "write"

export type ReportStatus =
  | "idle"
  | "started"
  | "in_progress"
  | "completed"
  | "failed"

export type ReportRequest = {
  topic: string
  phase?: ReportPhase | null
  session_id?: string | null
  use_knowledge_graph?: boolean
  stream?: boolean
  conversation_id?: string | null
  classify_only?: boolean
  model_name?: string
}

export type ReportResponse = {
  session_id: string
  status: ReportStatus
  topic: string
  phases: ReportPhase[]
  message: string
  action?: "plan" | "answer"
  conversation_id?: string
}

export type ReportStatusResponse = {
  session_id: string
  status: ReportStatus
  phases_completed: ReportPhase[]
  output_files: string[]
  created_at?: string | null
  current_phase?: ReportPhase | null
  current_stage?: string | null
  message?: string | null
  activities?: ResearchActivity[]
  activity_count?: number
  updated_at?: number | null
}

export type SearchResultItem = {
  title: string
  url: string
}

export type ResearchActivity = {
  id: string
  type: "web" | "local" | "finance" | "facts" | "output" | "info" | string
  message: string
  timestamp: number
  stage?: string
  phase?: ReportPhase
  query?: string
  results?: SearchResultItem[]
  result_count?: number
  ticker?: string
  count?: number
  section?: string
  filename?: string
}

export type ProgressEvent = {
  stage: string
  message: string
  phase?: ReportPhase
  type?: string
  query?: string
  results?: SearchResultItem[]
  result_count?: number
  ticker?: string
  count?: number
  section?: string
  filename?: string
}

export type ReportStreamEvent =
  | {
      type: "started"
      session_id: string
      phases: ReportPhase[]
      conversation_id?: string
    }
  | { type: "heartbeat"; session_id: string }
  | { type: "progress"; data: ProgressEvent; activity?: ResearchActivity }
  | {
      type: "completed"
      session_id: string
      output_files: string[]
      message: string
      conversation_id?: string
    }
  | {
      type: "error"
      session_id: string
      error: string
      message: string
      conversation_id?: string
    }

export type ReportGenerationState = {
  status: ReportStatus
  sessionId: string | null
  topic: string
  phases: ReportPhase[]
  phases_completed: ReportPhase[]
  currentPhase: ReportPhase | null
  currentStage: string | null
  outputFiles: string[]
  activities: ResearchActivity[]
  error: string | null
  message: string | null
}
