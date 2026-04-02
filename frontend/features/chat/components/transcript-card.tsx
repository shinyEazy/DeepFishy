import type { TranscriptMessage } from "@/features/chat/types"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function TranscriptCard({ role, body }: TranscriptMessage) {
  const isAssistant = role === "assistant"

  return (
    <div
      className={cn(
        "flex w-full",
        isAssistant ? "justify-start" : "justify-end"
      )}
    >
      <Card
        className={cn(
          "border transition-all duration-300",
          isAssistant
            ? "inline-flex w-fit max-w-[min(80%,48rem)] border-slate-200 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)]"
            : "inline-flex w-fit max-w-[min(75%,42rem)] border-transparent bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-[0_4px_14px_0_rgba(79,70,229,0.3)]"
        )}
      >
        <CardContent className="flex flex-col gap-4">
          <p
            className={cn(
              "text-sm leading-7 break-words whitespace-pre-wrap",
              isAssistant ? "text-slate-600" : "text-white/90"
            )}
          >
            {body}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
