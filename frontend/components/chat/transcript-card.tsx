import { BrainCircuit, MessageSquareText } from "lucide-react"

import { ModeBadge } from "@/components/chat/mode-badge"
import type { TranscriptMessage } from "@/components/chat/mock-data"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function TranscriptCard({
  role,
  mode,
  label,
  title,
  body,
  meta,
  bullets,
  references,
}: TranscriptMessage) {
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
          "w-full max-w-3xl border transition-all duration-300",
          isAssistant
            ? "border-slate-200 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)] hover:-translate-y-1 hover:shadow-[0_10px_25px_-5px_rgba(79,70,229,0.15)]"
            : "border-transparent bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-[0_4px_14px_0_rgba(79,70,229,0.3)]"
        )}
      >
        <CardHeader className="gap-3">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                "flex size-10 shrink-0 items-center justify-center rounded-xl border",
                isAssistant
                  ? "border-indigo-100/50 bg-indigo-50 text-indigo-600"
                  : "border-white/20 bg-white/10 text-white"
              )}
            >
              {isAssistant ? (
                <BrainCircuit className="size-4" />
              ) : (
                <MessageSquareText className="size-4" />
              )}
            </div>

            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <p
                  className={cn(
                    "text-xs font-medium tracking-[0.14em] uppercase",
                    isAssistant ? "text-primary/70" : "text-white/72"
                  )}
                >
                  {label}
                </p>
                <ModeBadge mode={mode} inverted={!isAssistant} />
              </div>
              <CardTitle
                className={cn(
                  "text-base leading-tight",
                  isAssistant ? "text-foreground" : "text-white"
                )}
              >
                {title}
              </CardTitle>
            </div>
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-4">
          <p
            className={cn(
              "text-sm leading-7",
              isAssistant ? "text-slate-600" : "text-white/90"
            )}
          >
            {body}
          </p>

          {bullets?.length ? (
            <div className="grid gap-3 md:grid-cols-3">
              {bullets.map((item) => (
                <div
                  key={item}
                  className={cn(
                    "rounded-xl border p-3 text-sm leading-6 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm",
                    isAssistant
                      ? "border-slate-200 bg-slate-50 text-slate-700"
                      : "border-white/14 bg-white/10 text-white/90"
                  )}
                >
                  {item}
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>

        <CardFooter
          className={cn(
            "flex flex-col items-start gap-3 border-t md:flex-row md:items-center md:justify-between",
            isAssistant
              ? "border-slate-200 bg-slate-50"
              : "border-white/12 bg-white/10"
          )}
        >
          <p
            className={cn(
              "text-xs",
              isAssistant ? "text-slate-500" : "text-white/74"
            )}
          >
            {meta}
          </p>

          {references?.length ? (
            <div className="flex flex-wrap gap-2">
              {references.map((item) => (
                <Badge
                  key={item}
                  variant={isAssistant ? "outline" : "secondary"}
                  className={cn(
                    "rounded-full px-2.5",
                    !isAssistant && "bg-white text-primary"
                  )}
                >
                  {item}
                </Badge>
              ))}
            </div>
          ) : null}
        </CardFooter>
      </Card>
    </div>
  )
}
