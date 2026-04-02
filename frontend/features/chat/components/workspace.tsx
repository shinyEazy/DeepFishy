"use client"

import { useState } from "react"

import { ChatMainPanel } from "@/features/chat/components/main-panel"
import { ChatSidebar } from "@/features/chat/components/sidebar"
import { defaultSessionId } from "@/features/chat/data/mock-sessions"
import { useChatSession } from "@/features/chat/hooks/use-chat-session"
import { cn } from "@/lib/utils"

export function ChatWorkspace({
  activeSessionId = defaultSessionId,
}: {
  activeSessionId?: string
}) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const { session, transcript, setTranscript } = useChatSession(activeSessionId)

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
            activeSessionId={session.id}
            collapsed={isSidebarCollapsed}
            onToggle={() => setIsSidebarCollapsed((value) => !value)}
          />
          <ChatMainPanel
            session={session}
            transcript={transcript}
            onTranscriptChange={setTranscript}
          />
        </div>
      </div>
    </main>
  )
}
