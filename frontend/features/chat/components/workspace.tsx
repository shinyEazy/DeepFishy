"use client"

import { useEffect, useState } from "react"

import { ChatMainPanel } from "@/features/chat/components/main-panel"
import { ChatSidebar } from "@/features/chat/components/sidebar"
import { newSessionId } from "@/features/chat/data/session-defaults"
import { useChatSession } from "@/features/chat/hooks/use-chat-session"
import { cn } from "@/lib/utils"

export function ChatWorkspace({
  activeSessionId,
}: {
  activeSessionId?: string
}) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [selectedSessionId, setSelectedSessionId] = useState(activeSessionId)
  const {
    sessions,
    resolvedSessionId,
    isLoadingSessions,
    session,
    transcript,
    setTranscript,
    setSessionMode,
    startDraftSession,
    promoteDraftSession,
  } = useChatSession(selectedSessionId)

  useEffect(() => {
    setSelectedSessionId(activeSessionId)
  }, [activeSessionId])

  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search)
      setSelectedSessionId(params.get("session") ?? undefined)
    }

    window.addEventListener("popstate", handlePopState)
    return () => {
      window.removeEventListener("popstate", handlePopState)
    }
  }, [])

  useEffect(() => {
    if (!resolvedSessionId || resolvedSessionId === selectedSessionId) {
      return
    }

    const nextUrl = new URL(window.location.href)
    nextUrl.searchParams.set("session", resolvedSessionId)
    window.history.replaceState({}, "", nextUrl)
    setSelectedSessionId(resolvedSessionId)
  }, [resolvedSessionId, selectedSessionId])

  return (
    <main className="h-svh overflow-hidden page-surface relative">
      <div className="absolute top-[-10%] left-[-10%] h-[500px] w-[500px] soft-orb z-0 opacity-50"></div>
      <div className="absolute right-[-10%] bottom-[-10%] h-[600px] w-[600px] soft-orb z-0 opacity-30"></div>

      <div className="relative z-10 flex h-full flex-col px-4 py-3">
        <div
          className={cn(
            "grid min-h-0 flex-1 gap-4 pt-2",
            isSidebarCollapsed
              ? "xl:grid-cols-[88px_minmax(0,1fr)]"
              : "xl:grid-cols-[440px_minmax(0,1fr)]"
          )}
        >
          <ChatSidebar
            sessions={sessions}
            activeSessionId={resolvedSessionId ?? ""}
            isLoading={isLoadingSessions}
            collapsed={isSidebarCollapsed}
            onToggle={() => setIsSidebarCollapsed((value) => !value)}
            onCreateSession={() => {
              startDraftSession()
              const nextUrl = new URL(window.location.href)
              nextUrl.searchParams.set("session", newSessionId)
              window.history.pushState({}, "", nextUrl)
              setSelectedSessionId(newSessionId)
            }}
            onSelectSession={(sessionId) => {
              const nextUrl = new URL(window.location.href)
              nextUrl.searchParams.set("session", sessionId)
              window.history.pushState({}, "", nextUrl)
              setSelectedSessionId(sessionId)
            }}
          />
          <ChatMainPanel
            session={session}
            transcript={transcript}
            onTranscriptChange={setTranscript}
            onModeChange={setSessionMode}
            onSessionChange={(sessionId) => {
              if (selectedSessionId === newSessionId) {
                promoteDraftSession(sessionId)
              }
              if (sessionId === selectedSessionId) {
                return
              }

              const nextUrl = new URL(window.location.href)
              nextUrl.searchParams.set("session", sessionId)
              window.history.replaceState({}, "", nextUrl)
              setSelectedSessionId(sessionId)
            }}
          />
        </div>
      </div>
    </main>
  )
}
