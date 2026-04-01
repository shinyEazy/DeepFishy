"use client"

import { useState } from "react"

import {
  defaultSessionId,
  getSessionContent,
} from "@/components/chat/mock-data"
import { ChatMainPanel } from "@/components/chat/main-panel"
import { ChatSidebar } from "@/components/chat/sidebar"
import { cn } from "@/lib/utils"

export function ChatWorkspace({
  activeSessionId = defaultSessionId,
}: {
  activeSessionId?: string
}) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const session = getSessionContent(activeSessionId)

  return (
    <main className="h-svh overflow-hidden page-surface relative">
      {/* Background Orbs for atmospheric depth */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] soft-orb opacity-50 z-0"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[600px] h-[600px] soft-orb opacity-30 z-0"></div>

      <div className="flex h-full flex-col px-4 py-3 relative z-10">
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
          <ChatMainPanel session={session} />
        </div>
      </div>
    </main>
  )
}
