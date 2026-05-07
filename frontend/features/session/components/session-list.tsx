import { Button } from "@/components/ui/button"
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
      onClick={() => onSelect?.(id)}
      className={cn(
        "group h-auto w-full min-w-0 justify-start overflow-hidden rounded-xl border px-3 py-2.5 text-left",
        active
          ? "border-indigo-100 bg-gradient-to-r from-indigo-50 to-violet-50 font-semibold text-indigo-800 hover:text-indigo-800"
          : "border-transparent font-medium text-slate-600 hover:border-slate-200 hover:bg-slate-50 hover:text-slate-950"
      )}
    >
      <div className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)] items-start gap-2.5">
        <p className="truncate text-sm leading-5">{title}</p>
      </div>
    </Button>
  )
}

export function SessionList({
  sessions,
  activeSessionId,
  isLoading = false,
  onSelectSession,
  onCloseMobile,
}: {
  sessions: SessionSummary[]
  activeSessionId: string
  isLoading?: boolean
  onSelectSession?: (sessionId: string) => void
  onCloseMobile?: () => void
}) {
  return (
    <section className="flex flex-col gap-2">
      <p className="px-2 text-[0.65rem] font-bold tracking-widest text-slate-400 uppercase">
        Lịch sử trò chuyện
      </p>
      <div className="flex flex-col gap-1">
        {isLoading ? (
          <p className="px-3 py-3 text-center text-sm text-slate-400">
            Đang tải phiên...
          </p>
        ) : sessions.length > 0 ? (
          sessions.map((session) => (
            <SessionButton
              key={session.id}
              id={session.id}
              title={session.title}
              active={session.id === activeSessionId}
              onSelect={(id) => {
                onSelectSession?.(id)
                onCloseMobile?.()
              }}
            />
          ))
        ) : (
          <p className="px-3 py-3 text-center text-sm text-slate-400">
            Chưa có phiên nào.
          </p>
        )}
      </div>
    </section>
  )
}
