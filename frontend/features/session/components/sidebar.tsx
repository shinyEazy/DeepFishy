"use client"

import { ChevronLeft, Fish, Plus, MessageSquareText, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { SessionSummary } from "@/features/chat/types"
import { cn } from "@/lib/utils"

function SessionButton({
  id,
  title,
  active = false,
  onSelect,
}: Pick<SessionSummary, "id" | "title"> & {
  active?: boolean
  onSelect?: (sessionId: string) => void
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      title={title}
      aria-current={active ? "page" : undefined}
      onClick={() => onSelect?.(id)}
      className={cn(
        "group h-auto w-full min-w-0 justify-start rounded-xl border px-3 py-2.5 text-left whitespace-normal",
        active
          ? "border-indigo-100 bg-gradient-to-r from-indigo-50 to-violet-50 font-semibold text-indigo-800 shadow-[0_6px_16px_rgba(79,70,229,0.14)] hover:text-indigo-800"
          : "border-transparent font-medium text-slate-600 hover:border-slate-200 hover:bg-slate-50 hover:text-slate-950"
      )}
    >
      <div className="flex min-w-0 items-start gap-2.5">
        <div
          className={cn(
            "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-all duration-200",
            active
              ? "bg-white text-indigo-600 shadow-[0_2px_8px_rgba(79,70,229,0.15)]"
              : "bg-slate-100 text-slate-400 group-hover:bg-indigo-50 group-hover:text-indigo-500"
          )}
        >
          <MessageSquareText className="size-4 stroke-2" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm leading-5 break-words">{title}</p>
        </div>
      </div>
    </Button>
  )
}

function SidebarContent({
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
  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header */}
      <div
        className={cn(
          "flex shrink-0 border-b border-slate-100/80 px-4 py-3.5",
          collapsed && !isMobile
            ? "justify-center"
            : "items-center justify-between"
        )}
      >
        {!collapsed || isMobile ? (
          <div className="flex items-center gap-2.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-[0_2px_8px_rgba(79,70,229,0.25)]">
              <Fish className="size-4 stroke-[2.5] text-white" />
            </div>
            <h2 className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-sm font-bold tracking-tight text-transparent">
              DeepFishy
            </h2>
          </div>
        ) : (
          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-[0_2px_8px_rgba(79,70,229,0.25)]">
            <Fish className="size-4 stroke-[2.5] text-white" />
          </div>
        )}
        <div className="flex items-center gap-1">
          {isMobile ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              onClick={onCloseMobile}
              className="text-slate-400 hover:bg-indigo-50 hover:text-indigo-700"
              aria-label="Đóng"
            >
              <X className="size-5 stroke-2" />
            </Button>
          ) : (
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              onClick={onToggle}
              aria-expanded={!collapsed}
              aria-label={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
              className="text-slate-400 hover:bg-indigo-50 hover:text-indigo-700"
            >
              <ChevronLeft
                className={cn(
                  "size-5 stroke-2 transition-transform duration-300",
                  collapsed && "rotate-180"
                )}
              />
            </Button>
          )}
        </div>
      </div>

      {/* Session list */}
      <ScrollArea
        className={cn(
          "min-h-0 flex-1",
          collapsed && !isMobile ? "hidden" : "block"
        )}
      >
        <div className="flex flex-col gap-3.5 px-3.5 py-3.5">
          <Button
            type="button"
            variant="outline"
            aria-label="Tạo cuộc trò chuyện mới"
            onClick={() => {
              onCreateSession?.()
              onCloseMobile?.()
            }}
            className="h-auto w-full min-w-0 justify-start gap-2.5 rounded-xl border-indigo-100 bg-indigo-50/70 px-3 py-2.5 font-semibold text-indigo-700 shadow-sm hover:border-indigo-200 hover:bg-indigo-100 hover:text-indigo-700"
          >
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-white text-indigo-600 shadow-[0_2px_8px_rgba(79,70,229,0.12)] transition-colors duration-200">
              <Plus className="size-4 stroke-2" />
            </div>
            <span className="min-w-0 flex-1 truncate text-left">
              Cuộc trò chuyện mới
            </span>
          </Button>

          <section className="flex flex-col gap-2">
            <p className="px-2 font-mono text-[0.65rem] font-bold tracking-widest text-slate-400 uppercase">
              Phiên hiện tại
            </p>
            <div className="flex flex-col gap-1">
              {isLoading ? (
                <div className="flex flex-col gap-2 px-3 py-2">
                  <div className="h-4 w-3/4 animate-pulse rounded-md bg-slate-200" />
                  <div className="h-4 w-1/2 animate-pulse rounded-md bg-slate-200" />
                </div>
              ) : sessions.length > 0 ? (
                sessions.map((session, index) => (
                  <div
                    key={session.id}
                    style={{
                      opacity: 0,
                      animation: `fadeInUp 0.3s ease forwards`,
                      animationDelay: `${index * 40}ms`,
                    }}
                  >
                    <SessionButton
                      id={session.id}
                      title={session.title}
                      active={session.id === activeSessionId}
                      onSelect={(id) => {
                        onSelectSession?.(id)
                        onCloseMobile?.()
                      }}
                    />
                  </div>
                ))
              ) : (
                <p className="px-3 py-3 text-center text-sm text-slate-400">
                  Chưa có phiên nào.
                </p>
              )}
            </div>
          </section>
        </div>
      </ScrollArea>
    </div>
  )
}

export function ChatSidebar({
  sessions,
  className,
  activeSessionId,
  isLoading = false,
  collapsed = false,
  onToggle,
  onCreateSession,
  onSelectSession,
}: {
  sessions: SessionSummary[]
  className?: string
  activeSessionId: string
  isLoading?: boolean
  collapsed?: boolean
  onToggle?: () => void
  onCreateSession?: () => void
  onSelectSession?: (sessionId: string) => void
}) {
  return (
    <aside
      className={cn(
        "min-h-0 overflow-hidden rounded-xl border border-slate-200/80 bg-white/95 shadow-[0_12px_32px_-18px_rgba(79,70,229,0.45)] ring-1 ring-white/60 backdrop-blur-md transition-all duration-300",
        className
      )}
    >
      <SidebarContent
        sessions={sessions}
        activeSessionId={activeSessionId}
        isLoading={isLoading}
        collapsed={collapsed}
        onToggle={onToggle}
        onCreateSession={onCreateSession}
        onSelectSession={onSelectSession}
      />
    </aside>
  )
}

export function ChatSidebarDrawer({
  sessions,
  activeSessionId,
  isLoading = false,
  isOpen = false,
  onClose,
  onCreateSession,
  onSelectSession,
}: {
  sessions: SessionSummary[]
  activeSessionId: string
  isLoading?: boolean
  isOpen?: boolean
  onClose?: () => void
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
          activeSessionId={activeSessionId}
          isLoading={isLoading}
          isMobile
          onCloseMobile={onClose}
          onCreateSession={onCreateSession}
          onSelectSession={onSelectSession}
        />
      </SheetContent>
    </Sheet>
  )
}
