"use client"

import { useState } from "react"

import { getSessionContent } from "@/features/chat/data/mock-sessions"
import type { TranscriptMessage } from "@/features/chat/types"

export function useChatSession(activeSessionId?: string) {
  const session = getSessionContent(activeSessionId)
  const [sessionTranscripts, setSessionTranscripts] = useState<
    Record<string, TranscriptMessage[]>
  >({})

  const transcript = sessionTranscripts[session.id] ?? [...session.transcript]

  const setTranscript = (
    value:
      | TranscriptMessage[]
      | ((current: TranscriptMessage[]) => TranscriptMessage[])
  ) => {
    setSessionTranscripts((current) => {
      const currentTranscript = current[session.id] ?? [...session.transcript]
      const nextTranscript =
        typeof value === "function" ? value(currentTranscript) : value

      return {
        ...current,
        [session.id]: nextTranscript,
      }
    })
  }

  return {
    session,
    transcript,
    setTranscript,
  }
}
