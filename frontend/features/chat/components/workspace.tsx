"use client"

import { useEffect, useState } from "react"
import { Menu } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ChatMainPanel } from "@/features/chat/components/main-panel"
import { ReportSidebar } from "@/features/report/components/report-sidebar"
import {
  ChatSidebar,
  ChatSidebarDrawer,
} from "@/features/session/components/sidebar"
import { newSessionId } from "@/features/session/constants/session-defaults"
import { useChatSession } from "@/features/session/hooks/use-chat-session"
import { cn } from "@/lib/utils"

export function ChatWorkspace({
  activeSessionId,
}: {
  activeSessionId?: string
}) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false)
  const [openReportSessionId, setOpenReportSessionId] = useState<string | null>(
    null
  )
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

  const handleNewSession = () => {
    startDraftSession()
    const nextUrl = new URL(window.location.href)
    nextUrl.searchParams.set("session", newSessionId)
    window.history.pushState({}, "", nextUrl)
    setSelectedSessionId(newSessionId)
  }

  const handleSelectSession = (sessionId: string) => {
    const nextUrl = new URL(window.location.href)
    nextUrl.searchParams.set("session", sessionId)
    window.history.pushState({}, "", nextUrl)
    setSelectedSessionId(sessionId)
  }

  const openReportMessage = transcript.find(
    (message) => message.deepResearch?.sessionId === openReportSessionId
  )

  return (
    <main
      className="relative h-svh overflow-hidden"
      style={{
        background:
          "radial-gradient(circle at top right, rgba(99,102,241,0.10) 0%, transparent 28rem), radial-gradient(circle at 10% 0%, rgba(124,58,237,0.07) 0%, transparent 22rem), linear-gradient(180deg, #f8fafc, #f1f5f9)",
      }}
    >
      {/* Background decorative orbs - hidden on mobile */}
      <div className="pointer-events-none absolute top-[-12%] left-[-8%] z-0 hidden h-[500px] w-[500px] opacity-40 xl:block">
        <div
          className="h-full w-full rounded-full blur-[28px]"
          style={{
            background:
              "radial-gradient(circle, rgba(99,102,241,0.34) 0%, rgba(124,58,237,0.16) 38%, transparent 72%)",
            animation: "float 12s ease-in-out infinite",
          }}
        />
      </div>
      <div className="pointer-events-none absolute right-[-8%] bottom-[-15%] z-0 hidden h-[600px] w-[600px] opacity-25 xl:block">
        <div
          className="h-full w-full rounded-full blur-[28px]"
          style={{
            background:
              "radial-gradient(circle, rgba(99,102,241,0.34) 0%, rgba(124,58,237,0.16) 38%, transparent 72%)",
            animation: "float 12s ease-in-out infinite",
            animationDelay: "4s",
          }}
        />
      </div>
      <div className="pointer-events-none absolute top-[60%] left-[40%] z-0 hidden h-[300px] w-[300px] opacity-15 xl:block">
        <div
          className="h-full w-full rounded-full blur-[28px]"
          style={{
            background:
              "radial-gradient(circle, rgba(99,102,241,0.34) 0%, rgba(124,58,237,0.16) 38%, transparent 72%)",
            animation: "float 12s ease-in-out infinite",
            animationDelay: "8s",
          }}
        />
      </div>

      {/* Grid overlay - hidden on mobile */}
      <div
        className="pointer-events-none absolute inset-0 z-0 hidden opacity-40 xl:block"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
          maskImage: "linear-gradient(to bottom, black, transparent 88%)",
        }}
      />

      {/* Mobile header */}
      <header className="fixed top-0 right-0 left-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200/80 bg-white/82 px-4 [box-shadow:inset_0_1px_0_rgba(255,255,255,0.95),0_1px_3px_rgba(79,70,229,0.06)] backdrop-blur-[18px] xl:hidden">
        <Button
          type="button"
          variant="outline"
          size="icon-lg"
          onClick={() => setIsMobileDrawerOpen(true)}
          className="size-10 bg-white/90 text-slate-600 shadow-[0_2px_8px_rgba(79,70,229,0.1)] hover:bg-white hover:text-indigo-600"
          aria-label="Mở thanh bên"
        >
          <Menu className="stroke-2" />
        </Button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900">
            {session.title || "DeepFishy"}
          </p>
        </div>
      </header>

      {/* Mobile drawer */}
      <ChatSidebarDrawer
        sessions={sessions}
        activeSessionId={resolvedSessionId ?? ""}
        isLoading={isLoadingSessions}
        isOpen={isMobileDrawerOpen}
        onClose={() => setIsMobileDrawerOpen(false)}
        onCreateSession={handleNewSession}
        onSelectSession={handleSelectSession}
      />

      {/* Content */}
      <div className="relative z-10 flex h-full flex-col px-3 py-3 pt-14 xl:px-4 xl:py-3 xl:pt-3">
        <div
          className={cn(
            "grid min-h-0 flex-1 gap-3 xl:gap-4 xl:pt-2",
            openReportSessionId
              ? isSidebarCollapsed
                ? "xl:grid-cols-[88px_minmax(420px,0.8fr)_minmax(520px,1.2fr)]"
                : "xl:grid-cols-[380px_minmax(420px,0.8fr)_minmax(520px,1.2fr)]"
              : isSidebarCollapsed
                ? "xl:grid-cols-[88px_minmax(0,1fr)]"
                : "xl:grid-cols-[380px_minmax(0,1fr)]"
          )}
        >
          {/* Desktop sidebar */}
          <ChatSidebar
            sessions={sessions}
            activeSessionId={resolvedSessionId ?? ""}
            isLoading={isLoadingSessions}
            collapsed={isSidebarCollapsed}
            onToggle={() => setIsSidebarCollapsed((value) => !value)}
            onCreateSession={handleNewSession}
            onSelectSession={handleSelectSession}
            className="hidden xl:flex"
          />

          <ChatMainPanel
            session={session}
            transcript={transcript}
            onTranscriptChange={setTranscript}
            onModeChange={setSessionMode}
            onOpenReport={setOpenReportSessionId}
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
          <ReportSidebar
            sessionId={openReportSessionId}
            title={
              openReportMessage?.deepResearch?.topic ?? "Báo cáo nghiên cứu"
            }
            isOpen={Boolean(openReportSessionId)}
            onClose={() => setOpenReportSessionId(null)}
          />
        </div>
      </div>
    </main>
  )
}
