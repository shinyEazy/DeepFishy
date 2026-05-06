import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import type { TranscriptMessage } from "@/features/chat/types"
import { cn } from "@/lib/utils"

export function TranscriptCard({ role, body, label, meta }: TranscriptMessage) {
  const isAssistant = role === "assistant"

  return (
    <div
      className={cn(
        "flex w-full",
        isAssistant ? "justify-start" : "justify-end"
      )}
    >
      <div
        className={cn(
          "flex max-w-[95%] flex-col gap-1 xl:max-w-[min(80%,48rem)]",
          isAssistant ? "items-start" : "items-end"
        )}
      >
        {/* Label row */}
        <div
          className={cn(
            "flex items-center gap-1.5 px-1 text-[0.7rem] font-medium",
            isAssistant ? "text-slate-400" : "text-slate-400"
          )}
        >
          <span>{label}</span>
          {meta ? (
            <>
              <span className="text-slate-300">·</span>
              <span className="text-slate-300">{meta}</span>
            </>
          ) : null}
        </div>

        {/* Message card */}
        <div
          className={cn(
            "inline-flex max-w-full flex-col rounded-2xl border p-4 transition-all duration-300",
            isAssistant
              ? "border-slate-200/60 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)]"
              : "border-transparent bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-[0_4px_14px_0_rgba(79,70,229,0.3)]"
          )}
        >
          <div className="flex flex-col gap-3">
            {isAssistant ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ className, ...props }) => (
                    <h1
                      className={cn(
                        "text-lg font-bold tracking-tight text-slate-900",
                        className
                      )}
                      {...props}
                    />
                  ),
                  h2: ({ className, ...props }) => (
                    <h2
                      className={cn(
                        "text-base font-bold tracking-tight text-slate-900",
                        className
                      )}
                      {...props}
                    />
                  ),
                  h3: ({ className, ...props }) => (
                    <h3
                      className={cn(
                        "text-sm font-semibold text-slate-900",
                        className
                      )}
                      {...props}
                    />
                  ),
                  p: ({ className, ...props }) => (
                    <p
                      className={cn(
                        "text-sm leading-7 text-slate-600 [overflow-wrap:break-word] [word-break:normal]",
                        className
                      )}
                      {...props}
                    />
                  ),
                  ul: ({ className, ...props }) => (
                    <ul
                      className={cn(
                        "list-disc space-y-1.5 pl-5 text-sm leading-7 text-slate-600",
                        className
                      )}
                      {...props}
                    />
                  ),
                  ol: ({ className, ...props }) => (
                    <ol
                      className={cn(
                        "list-decimal space-y-1.5 pl-5 text-sm leading-7 text-slate-600",
                        className
                      )}
                      {...props}
                    />
                  ),
                  li: ({ className, ...props }) => (
                    <li className={cn("[overflow-wrap:break-word]", className)} {...props} />
                  ),
                  a: ({ className, ...props }) => (
                    <a
                      className={cn(
                        "font-medium text-indigo-600 underline underline-offset-2 transition-colors duration-200 hover:text-indigo-700",
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
                        "border-l-2 border-indigo-200 bg-indigo-50/50 pl-4 italic text-slate-500",
                        className
                      )}
                      {...props}
                    />
                  ),
                  code: ({ className, children, ...props }) => {
                    const isInline = !String(className ?? "").includes(
                      "language-"
                    )

                    if (isInline) {
                      return (
                        <code
                          className={cn(
                            "rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-indigo-700",
                            className
                          )}
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    }

                    return (
                      <code
                        className={cn("font-mono text-sm", className)}
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  },
                  pre: ({ className, ...props }) => (
                    <pre
                      className={cn(
                        "overflow-x-auto rounded-xl bg-slate-950/95 p-4 text-sm leading-6 text-slate-100 shadow-inner",
                        className
                      )}
                      {...props}
                    />
                  ),
                  strong: ({ className, ...props }) => (
                    <strong
                      className={cn(
                        "font-semibold text-slate-900",
                        className
                      )}
                      {...props}
                    />
                  ),
                  table: ({ className, ...props }) => (
                    <div className="overflow-x-auto">
                      <table
                        className={cn(
                          "w-full border-collapse text-sm",
                          className
                        )}
                        {...props}
                      />
                    </div>
                  ),
                  th: ({ className, ...props }) => (
                    <th
                      className={cn(
                        "border-b border-slate-200 px-3 py-2 text-left font-semibold text-slate-700",
                        className
                      )}
                      {...props}
                    />
                  ),
                  td: ({ className, ...props }) => (
                    <td
                      className={cn(
                        "border-b border-slate-100 px-3 py-2 text-slate-600",
                        className
                      )}
                      {...props}
                    />
                  ),
                  hr: ({ className, ...props }) => (
                    <hr
                      className={cn("my-3 border-slate-100", className)}
                      {...props}
                    />
                  ),
                }}
              >
                {body}
              </ReactMarkdown>
            ) : (
              <p className="text-sm leading-7 text-white/90 [overflow-wrap:break-word] [word-break:normal]">
                {body}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
