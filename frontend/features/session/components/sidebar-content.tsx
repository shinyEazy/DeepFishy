import { ScrollArea } from "@/components/ui/scroll-area"
import type { SessionSummary } from "@/features/chat/types"
import { cn } from "@/lib/utils"

import { NewSessionButton } from "./new-session-button"
import { SessionList } from "./session-list"
import { SidebarHeader } from "./sidebar-header"

export function SidebarContent({
  sessions,
  activeSessionId,
  isLoading,
  collapsed,
  onToggle,
  onCreateSession,
  onSelectSession,
  isMobile = false,
  onCloseMobile,
}: {
  sessions: SessionSummary[]
  activeSessionId: string
  isLoading?: boolean
  collapsed?: boolean
  onToggle?: () => void
  onCreateSession?: () => void
  onSelectSession?: (sessionId: string) => void
  isMobile?: boolean
  onCloseMobile?: () => void
}) {
  const showContent = !collapsed || isMobile

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <SidebarHeader
        collapsed={collapsed}
        isMobile={isMobile}
        onToggle={onToggle}
        onCloseMobile={onCloseMobile}
      />

      <ScrollArea
        className={cn(
          "min-h-0 flex-1 transition-all duration-300",
          showContent ? "opacity-100" : "pointer-events-none opacity-0"
        )}
      >
        <div
          className={cn(
            "flex flex-col gap-3.5 px-3.5 py-3.5 transition-all duration-300",
            showContent ? "translate-x-0" : "-translate-x-3"
          )}
        >
          <NewSessionButton
            onCreateSession={onCreateSession}
            onCloseMobile={onCloseMobile}
          />
          <SessionList
            sessions={sessions}
            activeSessionId={activeSessionId}
            isLoading={isLoading}
            onSelectSession={onSelectSession}
            onCloseMobile={onCloseMobile}
          />
        </div>
      </ScrollArea>
    </div>
  )
}
