import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { ChatModelOption } from "@/features/chat/lib/model-options"
import type { SessionSummary } from "@/features/chat/types"
import { cn } from "@/lib/utils"

import { SidebarContent } from "./sidebar-content"

export function ChatSidebar({
  sessions,
  modelOptions,
  selectedModel,
  className,
  activeSessionId,
  isLoading = false,
  collapsed = false,
  onToggle,
  onModelChange,
  onCreateSession,
  onSelectSession,
}: {
  sessions: SessionSummary[]
  modelOptions: ChatModelOption[]
  selectedModel: string
  className?: string
  activeSessionId: string
  isLoading?: boolean
  collapsed?: boolean
  onToggle?: () => void
  onModelChange: (model: string) => void
  onCreateSession?: () => void
  onSelectSession?: (sessionId: string) => void
}) {
  return (
    <aside
      className={cn(
        "min-h-0 rounded-xl border border-slate-200/80 bg-white/95 shadow-[0_12px_32px_-18px_rgba(79,70,229,0.45)] ring-1 ring-transparent backdrop-blur-md transition-all duration-300",
        collapsed ? "overflow-visible" : "overflow-hidden",
        className
      )}
    >
      <SidebarContent
        sessions={sessions}
        modelOptions={modelOptions}
        selectedModel={selectedModel}
        activeSessionId={activeSessionId}
        isLoading={isLoading}
        collapsed={collapsed}
        onToggle={onToggle}
        onModelChange={onModelChange}
        onCreateSession={onCreateSession}
        onSelectSession={onSelectSession}
      />
    </aside>
  )
}

export function ChatSidebarDrawer({
  sessions,
  modelOptions,
  selectedModel,
  activeSessionId,
  isLoading = false,
  isOpen = false,
  onClose,
  onModelChange,
  onCreateSession,
  onSelectSession,
}: {
  sessions: SessionSummary[]
  modelOptions: ChatModelOption[]
  selectedModel: string
  activeSessionId: string
  isLoading?: boolean
  isOpen?: boolean
  onClose?: () => void
  onModelChange: (model: string) => void
  onCreateSession?: () => void
  onSelectSession?: (sessionId: string) => void
}) {
  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose?.()}>
      <SheetContent
        side="left"
        showCloseButton={false}
        className="w-[min(92vw,360px)] gap-0 border-slate-200 bg-white/98 p-0 backdrop-blur-lg sm:max-w-none"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>DeepFishy sidebar</SheetTitle>
          <SheetDescription>
            Danh sách phiên trò chuyện và nút tạo phiên mới.
          </SheetDescription>
        </SheetHeader>
        <SidebarContent
          sessions={sessions}
          modelOptions={modelOptions}
          selectedModel={selectedModel}
          activeSessionId={activeSessionId}
          isLoading={isLoading}
          isMobile
          onCloseMobile={onClose}
          onModelChange={onModelChange}
          onCreateSession={onCreateSession}
          onSelectSession={onSelectSession}
        />
      </SheetContent>
    </Sheet>
  )
}
