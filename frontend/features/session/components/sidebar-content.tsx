import { ScrollArea } from "@/components/ui/scroll-area"
import type { ChatModelOption } from "@/features/chat/lib/model-options"
import type { SessionSummary } from "@/features/chat/types"
import { cn } from "@/lib/utils"

import { ModelSelector } from "./model-selector"
import { NewSessionButton } from "./new-session-button"
import { SessionList } from "./session-list"
import { SidebarHeader } from "./sidebar-header"

export function SidebarContent({
  sessions,
  modelOptions,
  selectedModel,
  activeSessionId,
  isLoading,
  collapsed,
  onToggle,
  onModelChange,
  onCreateSession,
  onSelectSession,
  isMobile = false,
  onCloseMobile,
}: {
  sessions: SessionSummary[]
  modelOptions: ChatModelOption[]
  selectedModel: string
  activeSessionId: string
  isLoading?: boolean
  collapsed?: boolean
  onToggle?: () => void
  onModelChange: (model: string) => void
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
          <ModelSelector
            options={modelOptions}
            selectedModel={selectedModel}
            onModelChange={onModelChange}
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
