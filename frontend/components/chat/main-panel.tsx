import { ArrowUp, Mic, Plus } from "lucide-react"

import { ModeBadge } from "@/components/chat/mode-badge"
import { TranscriptCard } from "@/components/chat/transcript-card"
import { type SessionContent } from "@/components/chat/mock-data"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export function ChatMainPanel({
  className,
  session,
}: {
  className?: string
  session: SessionContent
}) {
  return (
    <section
      className={cn(
        "min-h-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)]",
        className
      )}
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto bg-[linear-gradient(180deg,#ffffff,#f8fafc)] px-6 py-5">
          <div className="mx-auto flex max-w-4xl flex-col gap-4">
            {session.transcript.map((message) => (
              <TranscriptCard
                key={`${session.id}-${message.title}`}
                {...message}
              />
            ))}
          </div>
        </div>

        <div className="border-t bg-white px-6 py-5">
          <div className="mx-auto flex max-w-4xl flex-col gap-4">
            <div className="flex w-full items-center rounded-full border border-slate-200 bg-white px-5 py-3 shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)] transition-all duration-300 focus-within:border-indigo-500 focus-within:shadow-[0_10px_25px_-5px_rgba(79,70,229,0.15)] focus-within:ring-2 focus-within:ring-indigo-500 hover:shadow-[0_10px_25px_-5px_rgba(79,70,229,0.15)]">
              <div className="flex w-full items-center gap-3">
                <button
                  type="button"
                  className="flex size-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition-all duration-200 hover:bg-slate-100 hover:text-indigo-600"
                >
                  <Plus className="size-4" />
                </button>

                <input
                  className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
                  defaultValue={session.inputPlaceholder}
                />

                <button
                  type="button"
                  className="flex size-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition-all duration-200 hover:bg-slate-100 hover:text-indigo-600"
                >
                  <Mic className="size-4" />
                </button>

                <button
                  type="button"
                  className="hero-button flex size-8 shrink-0 items-center justify-center rounded-full text-white transition-all duration-200 hover:-translate-y-0.5"
                >
                  <ArrowUp className="size-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
