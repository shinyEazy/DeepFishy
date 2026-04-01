"use client"

import Link from "next/link"
import { ChevronLeft } from "lucide-react"

import { sessionGroups, type SessionSummary } from "@/components/chat/mock-data"
import { cn } from "@/lib/utils"

function SessionButton({
  id,
  title,
  preview,
  active = false,
}: Pick<SessionSummary, "id" | "title" | "preview"> & { active?: boolean }) {
  return (
    <Link
      href={`/?session=${id}`}
      scroll={false}
      className={cn(
        "block rounded-lg px-3 py-2 text-sm transition-all duration-200",
        active
          ? "bg-indigo-50 font-medium text-indigo-700"
          : "text-slate-500 hover:translate-x-1 hover:bg-slate-50 hover:text-slate-900"
      )}
    >
      <p className="text-sm leading-6">{title}</p>
    </Link>
  )
}

export function ChatSidebar({
  className,
  activeSessionId,
  collapsed = false,
  onToggle,
}: {
  className?: string
  activeSessionId: string
  collapsed?: boolean
  onToggle?: () => void
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
          {sessionGroups.map((group) => (
            <section key={group.label} className="flex flex-col gap-3">
              <p className="text-xs font-semibold tracking-[0.08em] text-slate-500 uppercase">
                {group.label}
              </p>
              <div className="flex flex-col gap-1">
                {group.sessions.map((session) => (
                  <SessionButton
                    key={session.id}
                    id={session.id}
                    title={session.title}
                    preview={session.preview}
                    active={session.id === activeSessionId}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </aside>
  )
}
