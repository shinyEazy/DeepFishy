import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

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
          {isAssistant ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ className, ...props }) => (
                  <h1
                    className={cn("text-lg font-semibold text-slate-900", className)}
                    {...props}
                  />
                ),
                h2: ({ className, ...props }) => (
                  <h2
                    className={cn("text-base font-semibold text-slate-900", className)}
                    {...props}
                  />
                ),
                h3: ({ className, ...props }) => (
                  <h3
                    className={cn("text-sm font-semibold text-slate-900", className)}
                    {...props}
                  />
                ),
                p: ({ className, ...props }) => (
                  <p
                    className={cn(
                      "text-sm leading-7 break-words whitespace-pre-wrap text-slate-600",
                      className
                    )}
                    {...props}
                  />
                ),
                ul: ({ className, ...props }) => (
                  <ul
                    className={cn(
                      "list-disc space-y-2 pl-5 text-sm leading-7 text-slate-600",
                      className
                    )}
                    {...props}
                  />
                ),
                ol: ({ className, ...props }) => (
                  <ol
                    className={cn(
                      "list-decimal space-y-2 pl-5 text-sm leading-7 text-slate-600",
                      className
                    )}
                    {...props}
                  />
                ),
                li: ({ className, ...props }) => (
                  <li className={cn("break-words", className)} {...props} />
                ),
                a: ({ className, ...props }) => (
                  <a
                    className={cn(
                      "text-indigo-600 underline underline-offset-2 hover:text-indigo-700",
                      className
                    )}
                    target="_blank"
                    rel="noreferrer"
                    {...props}
                  />
                ),
                blockquote: ({ className, ...props }) => (
                  <blockquote
                    className={cn(
                      "border-l-2 border-slate-200 pl-4 italic text-slate-500",
                      className
                    )}
                    {...props}
                  />
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !String(className ?? "").includes("language-")

                  if (isInline) {
                    return (
                      <code
                        className={cn(
                          "rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-slate-700",
                          className
                        )}
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  }

                  return (
                    <code className={cn("font-mono text-sm", className)} {...props}>
                      {children}
                    </code>
                  )
                },
                pre: ({ className, ...props }) => (
                  <pre
                    className={cn(
                      "overflow-x-auto rounded-xl bg-slate-950/95 p-4 text-sm text-slate-100",
                      className
                    )}
                    {...props}
                  />
                ),
                strong: ({ className, ...props }) => (
                  <strong className={cn("font-semibold text-slate-900", className)} {...props} />
                ),
              }}
            >
              {body}
            </ReactMarkdown>
          ) : (
            <p className="text-sm leading-7 break-words whitespace-pre-wrap text-white/90">
              {body}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
