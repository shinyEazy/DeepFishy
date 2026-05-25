"use client"

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useState,
} from "react"

import {
  getSession,
  listSessions,
} from "@/features/session/api/sessions"
import {
  defaultInputPlaceholder,
  defaultSessionMode,
  defaultSessionTitle,
  newSessionId,
} from "@/features/session/constants/session-defaults"
import {
  mapSessionMessageToTranscript,
  mapTranscriptToSessionMessage,
} from "@/features/chat/lib/messages"
import type {
  SessionContent,
  SessionDetail,
  SessionSummary,
  TranscriptMessage,
} from "@/features/chat/types"

function buildSessionTitle(seedText: string, maxLength = 80) {
  const normalized = seedText.replace(/\s+/g, " ").trim()
  if (!normalized) {
    return defaultSessionTitle
  }

  if (normalized.length <= maxLength) {
    return normalized
  }

  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`
}

export function useChatSession(activeSessionId?: string) {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionDetails, setSessionDetails] = useState<Record<string, SessionDetail>>(
    {}
  )
  const [sessionTranscripts, setSessionTranscripts] = useState<
    Record<string, TranscriptMessage[]>
  >({})
  const [draftTranscript, setDraftTranscript] = useState<TranscriptMessage[]>([])
  const [fallbackSessionId, setFallbackSessionId] = useState<string | null>(null)
  const [missingSessionIds, setMissingSessionIds] = useState<
    Record<string, true>
  >({})
  const [isLoadingSessions, setIsLoadingSessions] = useState(true)
  const [isLoadingSession, setIsLoadingSession] = useState(false)
  const [sessionMode, setSessionMode] = useState(defaultSessionMode)

  const isDraftSession = activeSessionId === newSessionId
  const resolvedSessionId =
    isDraftSession
      ? undefined
      : activeSessionId && !missingSessionIds[activeSessionId]
      ? activeSessionId
      : fallbackSessionId ?? sessions[0]?.id

  const refreshSessions = useCallback(async () => {
    const data = await listSessions()
    setSessions(data.sessions)
    return data.sessions
  }, [])

  const refreshSession = useCallback(async (sessionId: string) => {
    const detail = await getSession(sessionId)
    const mappedTranscript = detail.messages.map((message) =>
      mapSessionMessageToTranscript(message, defaultSessionMode)
    )

    setSessionDetails((current) => ({
      ...current,
      [detail.id]: detail,
    }))
    setSessionTranscripts((current) => {
      const currentTranscript = current[detail.id]
      if (currentTranscript && currentTranscript.length > mappedTranscript.length) {
        return current
      }

      return {
        ...current,
        [detail.id]: mappedTranscript,
      }
    })

    return detail
  }, [])

  const startDraftSession = useCallback(() => {
    setDraftTranscript([])
  }, [])

  const promoteDraftSession = useCallback(
    (sessionId: string, transcriptOverride?: TranscriptMessage[]) => {
      const transcriptToPromote = transcriptOverride ?? draftTranscript
      if (!transcriptToPromote.length) {
        return
      }

      const timestamp = new Date().toISOString()
      const firstUserMessage = transcriptToPromote.find(
        (message) => message.role === "user"
      )
      const title = buildSessionTitle(firstUserMessage?.body ?? "")

      setSessionTranscripts((current) => ({
        ...current,
        [sessionId]: transcriptToPromote,
      }))
      setSessionDetails((current) => ({
        ...current,
        [sessionId]: {
          id: sessionId,
          title,
          createdAt: timestamp,
          updatedAt: timestamp,
          messages: transcriptToPromote.map(mapTranscriptToSessionMessage),
        },
      }))
      setSessions((current) => {
        const existing = current.find((session) => session.id === sessionId)
        const nextSummary: SessionSummary = {
          id: sessionId,
          title: existing?.title ?? title,
          createdAt: existing?.createdAt ?? timestamp,
          updatedAt: timestamp,
          messageCount: transcriptToPromote.length,
        }

        return [
          nextSummary,
          ...current.filter((session) => session.id !== sessionId),
        ]
      })
      setDraftTranscript([])
      setFallbackSessionId(sessionId)
    },
    [draftTranscript]
  )

  useEffect(() => {
    let cancelled = false

    const loadSessions = async () => {
      try {
        setIsLoadingSessions(true)
        await refreshSessions()
      } catch (error) {
        if (!cancelled) {
          console.error(error)
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSessions(false)
        }
      }
    }

    void loadSessions()

    return () => {
      cancelled = true
    }
  }, [refreshSessions])

  useEffect(() => {
    if (
      !resolvedSessionId ||
      sessionDetails[resolvedSessionId] ||
      sessionTranscripts[resolvedSessionId]?.length
    ) {
      return
    }

    let cancelled = false

    const loadSession = async () => {
      try {
        setIsLoadingSession(true)
        await refreshSession(resolvedSessionId)
      } catch (error) {
        if (!cancelled) {
          if (
            activeSessionId === resolvedSessionId &&
            typeof error === "object" &&
            error !== null &&
            "status" in error &&
            error.status === 404
          ) {
            setMissingSessionIds((current) => ({
              ...current,
              [resolvedSessionId]: true,
            }))
          } else {
            console.error(error)
          }
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSession(false)
        }
      }
    }

    void loadSession()

    return () => {
      cancelled = true
    }
  }, [
    activeSessionId,
    refreshSession,
    resolvedSessionId,
    sessionDetails,
    sessionTranscripts,
  ])

  const transcript = resolvedSessionId
    ? sessionTranscripts[resolvedSessionId] ?? []
    : draftTranscript

  const activeSummary = resolvedSessionId
    ? sessions.find((session) => session.id === resolvedSessionId)
    : undefined

  const session: SessionContent = {
    id: resolvedSessionId,
    title:
      (resolvedSessionId ? sessionDetails[resolvedSessionId]?.title : undefined) ??
      activeSummary?.title ??
      defaultSessionTitle,
    mode: sessionMode,
    inputPlaceholder: defaultInputPlaceholder,
    transcript,
  }

  const setTranscript: Dispatch<SetStateAction<TranscriptMessage[]>> = (
    value
  ) => {
    if (!resolvedSessionId) {
      setDraftTranscript((current) =>
        typeof value === "function" ? value(current) : value
      )
      return
    }

    setSessionTranscripts((current) => {
      const currentTranscript = current[resolvedSessionId] ?? []
      const nextTranscript =
        typeof value === "function" ? value(currentTranscript) : value

      return {
        ...current,
        [resolvedSessionId]: nextTranscript,
      }
    })
  }

  return {
    sessions,
    resolvedSessionId,
    isLoadingSessions,
    isLoadingSession,
    session,
    transcript,
    setTranscript,
    sessionMode,
    setSessionMode,
    refreshSessions,
    refreshSession,
    startDraftSession,
    promoteDraftSession,
  }
}
