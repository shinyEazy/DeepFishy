import {
  ChartNoAxesColumn,
  Clock3,
  FileSearch,
  Fish,
  SearchCheck,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import type { TranscriptMessage } from "@/features/chat/types"
import { cn } from "@/lib/utils"

export function TranscriptCard({
  role,
  body,
  label,
  meta,
  researchPlan,
  isLoading,
  onStartResearch,
  isStartingResearch = false,
}: TranscriptMessage & {
  onStartResearch?: (topic: string) => void
  isStartingResearch?: boolean
}) {
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
        <div className="flex items-center gap-2 px-1 text-[0.7rem] font-medium text-slate-500">
          {isAssistant ? (
            <Avatar className="size-5 rounded-md">
              <AvatarFallback className="rounded-md bg-gradient-to-br from-indigo-500 to-violet-600">
                <Fish className="size-3 text-white" />
              </AvatarFallback>
            </Avatar>
          ) : null}
          <span>{label}</span>
          {!isAssistant && meta ? (
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
              isLoading ? (
                <div className="flex items-center gap-3 text-sm text-slate-600">
                  <Spinner className="size-4 text-indigo-500" />
                  <span>{body}</span>
                </div>
              ) : (
                <>
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
                            "text-sm leading-7 [overflow-wrap:break-word] [word-break:normal] text-slate-600",
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
                        <li
                          className={cn(
                            "[overflow-wrap:break-word]",
                            className
                          )}
                          {...props}
                        />
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
                            "border-l-2 border-indigo-200 bg-indigo-50/50 pl-4 text-slate-500 italic",
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

                  {researchPlan ? (
                    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-slate-50 shadow-none">
                      <CardHeader>
                        <CardTitle className="text-lg leading-tight font-semibold text-slate-900">
                          Kế hoạch nghiên cứu
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="">
                        <div className="flex flex-col py-1">
                          {[
                            ...researchPlan.steps,
                            researchPlan.readyMessage,
                          ].map((step, index, steps) => {
                            const Icon =
                              index === 0
                                ? SearchCheck
                                : index === 1
                                  ? ChartNoAxesColumn
                                  : index === 2
                                    ? FileSearch
                                    : Clock3

                            return (
                              <div
                                key={step}
                                className="flex items-start gap-3 text-sm text-slate-700"
                              >
                                <div className="flex w-5 shrink-0 flex-col items-center">
                                  <Icon className="size-4 text-slate-700" />
                                  {index < steps.length - 1 ? (
                                    <div className="my-2 h-4 w-px bg-slate-300" />
                                  ) : null}
                                </div>
                                <div className="min-w-0 pb-5 font-medium text-slate-900 last:pb-0">
                                  {step}
                                </div>
                              </div>
                            )
                          })}
                        </div>

                        {researchPlan.awaitingConfirmation &&
                        onStartResearch ? (
                          <div className="mt-4 flex justify-end">
                            <Button
                              type="button"
                              onClick={() =>
                                onStartResearch(researchPlan.topic)
                              }
                              disabled={isStartingResearch}
                              className="rounded-full px-5"
                            >
                              {isStartingResearch
                                ? "Đang bắt đầu..."
                                : (researchPlan.startLabel ??
                                  "Bắt đầu nghiên cứu")}
                            </Button>
                          </div>
                        ) : null}
                      </CardContent>
                    </Card>
                  ) : null}
                </>
              )
            ) : (
              <p className="text-sm leading-7 [overflow-wrap:break-word] [word-break:normal] text-white/90">
                {body}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
