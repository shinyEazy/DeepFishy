"use client"

import { ChevronLeft, Plus } from "lucide-react"

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
    <button
      type="button"
      onClick={() => onSelect?.(id)}
      className={cn(
        "block w-full rounded-lg px-3 py-2 text-left text-sm transition-all duration-200",
        active
          ? "bg-indigo-50 font-medium text-indigo-700"
          : "text-slate-500 hover:translate-x-1 hover:bg-slate-50 hover:text-slate-900"
      )}
    >
      <p className="text-sm leading-6">{title}</p>
    </button>
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
        "min-h-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)] transition-all duration-300",
        className
      )}
    >
      <div className="flex h-full min-h-0 flex-col">
        <div
          className={cn(
            "flex border-b px-4 py-4",
            collapsed ? "justify-center" : "items-center justify-between"
          )}
        >
          {!collapsed ? (
            <h2 className="text-lg font-medium text-foreground">Lịch sử</h2>
          ) : null}
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
            className="flex size-9 items-center justify-center rounded-full text-muted-foreground transition-all duration-200 hover:bg-slate-100 hover:text-slate-900"
          >
            <ChevronLeft
              className={cn(
                "size-4 transition-transform duration-300",
                collapsed && "rotate-180"
              )}
            />
          </button>
        </div>

        <div
          className={cn(
            "min-h-0 flex-1 overflow-y-auto transition-all duration-300",
            collapsed
              ? "pointer-events-none w-0 opacity-0"
              : "flex flex-col gap-5 px-4 py-4 opacity-100"
          )}
        >
          <button
            type="button"
            onClick={onCreateSession}
            className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 transition-all duration-200 hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700"
          >
            <Plus className="size-4" />
            Cuộc trò chuyện mới
          </button>

          <section className="flex flex-col gap-3">
            <p className="text-xs font-semibold tracking-[0.08em] text-slate-500 uppercase">
              Lịch sử phiên
            </p>
            <div className="flex flex-col gap-1">
              {isLoading ? (
                <p className="px-3 py-2 text-sm text-slate-500">Đang tải phiên...</p>
              ) : sessions.length > 0 ? (
                sessions.map((session) => (
                  <SessionButton
                    key={session.id}
                    id={session.id}
                    title={session.title}
                    active={session.id === activeSessionId}
                    onSelect={onSelectSession}
                  />
                ))
              ) : (
                <p className="px-3 py-2 text-sm text-slate-500">
                  Chưa có phiên nào.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </aside>
  )
}
