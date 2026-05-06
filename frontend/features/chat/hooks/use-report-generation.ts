"use client"

import { useCallback, useState } from "react"

import { streamReportGeneration } from "@/features/chat/api/reports"
import type {
  ResearchActivity,
  ReportGenerationState,
  ReportPhase,
  ReportRequest,
} from "@/features/chat/types/report"

const initialState: ReportGenerationState = {
  status: "idle",
  sessionId: null,
  topic: "",
  phases: [],
  phases_completed: [],
  currentPhase: null,
  currentStage: null,
  outputFiles: [],
  activities: [],
  error: null,
  message: null,
}

export function useReportGeneration() {
  const [state, setState] = useState<ReportGenerationState>(initialState)

  const generate = useCallback(async (request: ReportRequest) => {
    const phases: ReportPhase[] = request.phase
      ? [request.phase]
      : ["build", "write"]

    setState({
      status: "started",
      sessionId: request.session_id ?? null,
      topic: request.topic,
      phases,
      phases_completed: [],
      currentPhase: phases[0],
      currentStage: null,
      outputFiles: [],
      activities: [],
      error: null,
      message: "Đang bắt đầu tạo báo cáo...",
    })

    try {
      await streamReportGeneration(request, {
        onStarted: (sessionId, startedPhases) => {
          setState((prev) => ({
            ...prev,
            sessionId,
            status: "in_progress",
            phases: startedPhases,
            currentPhase: startedPhases[0],
            message: `Đang chạy giai đoạn ${startedPhases[0]}...`,
          }))
        },
        onProgress: (event) => {
          setState((prev) => ({
            ...prev,
            currentStage: event.stage,
            activities: [
              ...prev.activities,
              {
                id: `activity-${Date.now()}`,
                type: (event.type as ResearchActivity["type"]) ?? "info",
                message: event.message,
                timestamp: Date.now(),
              },
            ],
            message: event.message,
          }))
        },
        onCompleted: (sessionId, outputFiles, message) => {
          setState((prev) => ({
            ...prev,
            sessionId,
            status: "completed",
            currentPhase: null,
            currentStage: null,
            phases_completed: prev.phases,
            outputFiles,
            message,
          }))
        },
        onError: (sessionId, error, message) => {
          setState((prev) => ({
            ...prev,
            sessionId,
            status: "failed",
            currentPhase: null,
            currentStage: null,
            error,
            message,
          }))
        },
      })
    } catch (error) {
      setState((prev) => ({
        ...prev,
        status: "failed",
        currentPhase: null,
        currentStage: null,
        error: error instanceof Error ? error.message : "Unknown error",
        message: "Tạo báo cáo thất bại",
      }))
    }
  }, [])

  const reset = useCallback(() => {
    setState(initialState)
  }, [])

  const viewReport = useCallback((sessionId: string) => {
    window.open(`/reports/${sessionId}`, "_blank")
  }, [])

  return {
    state,
    generate,
    reset,
    viewReport,
    isGenerating:
      state.status === "started" || state.status === "in_progress",
  }
}
