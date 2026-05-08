"use client"

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"
import { ArrowUp, Fish, Globe, RefreshCw, X } from "lucide-react"

import { streamChatResponse } from "@/features/chat/api/responses"
import {
  generateReport,
  getReportStatus,
  streamReportGeneration,
} from "@/features/report/api/reports"
import { DeepResearchProgress } from "@/features/report/components/deep-research-progress"
import { TranscriptCard } from "@/features/chat/components/transcript-card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import {
  createAssistantMessage,
  createResearchPlanMessage,
  createUserMessage,
} from "@/features/chat/lib/messages"
import type {
  Mode,
  ResearchActivity,
  ResearchPlan,
  SessionContent,
  TranscriptMessage,
} from "@/features/chat/types"
import type { ReportPhase } from "@/features/report/types"
import { cn } from "@/lib/utils"

let activityIdCounter = 0

function appendActivity(
  activities: ResearchActivity[],
  activity: ResearchActivity
) {
  if (activities.some((item) => item.id === activity.id)) {
    return activities
  }
  return [...activities, activity]
}

function mergeActivities(
  current: ResearchActivity[],
  incoming?: ResearchActivity[]
) {
  if (!incoming?.length) {
    return current
  }

  return incoming.reduce(appendActivity, current)
}

export function ChatMainPanel({
  className,
  session,
  transcript,
  onTranscriptChange,
  onModeChange,
  onSessionChange,
  onConversationUpdated,
  selectedModel,
  onOpenReport,
}: {
  className?: string
  session: SessionContent
  transcript: TranscriptMessage[]
  onTranscriptChange: Dispatch<SetStateAction<TranscriptMessage[]>>
  selectedModel: string
  onModeChange?: Dispatch<SetStateAction<Mode>>
  onSessionChange?: (
    sessionId: string,
    transcriptOverride?: TranscriptMessage[]
  ) => void
  onConversationUpdated?: () => void
  onOpenReport?: (sessionId: string) => void
}) {
  const [draft, setDraft] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const isNewSession = !session.id && transcript.length === 0

  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ block: "end" })
  }, [transcript, isSubmitting])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) {
      return
    }

    textarea.style.height = "0px"
    textarea.style.height = `${textarea.scrollHeight}px`
  }, [draft])

  const handleDeepResearch = useCallback(
    async (
      topic: string,
      options?: { appendUserMessage?: boolean; researchPlan?: ResearchPlan }
    ) => {
      const phases: ReportPhase[] = ["build", "write"]
      const shouldAppendUserMessage = options?.appendUserMessage ?? true
      const researchPlan = options?.researchPlan

      const userMessage = createUserMessage(topic, "deep")
      userMessage.title = "Nghiên cứu sâu"

      const assistantMessage: TranscriptMessage = {
        role: "assistant",
        mode: "deep",
        label: "DeepFishy",
        title: "Nghiên cứu sâu",
        body: "",
        meta: "Đang xử lý...",
        deepResearch: {
          status: "started",
          topic,
          phases,
          currentPhase: phases[0],
          currentStage: "classify",
          phasesCompleted: [],
          sessionId: null,
          activities: [
            {
              id: `activity-${++activityIdCounter}`,
              type: "info",
              message: "Đang phân loại chủ đề...",
              timestamp: Date.now(),
            },
          ],
          message: "Đang phân loại chủ đề...",
        },
      }

      onTranscriptChange((current) => [
        ...current,
        ...(shouldAppendUserMessage ? [userMessage] : []),
        assistantMessage,
      ])

      const pollReportStatus = async (sessionId: string) => {
        for (let i = 0; i < 240; i += 1) {
          let status
          try {
            status = await getReportStatus(sessionId)
          } catch {
            await new Promise((resolve) => setTimeout(resolve, 3000))
            continue
          }
          onTranscriptChange((current) => {
            const updated = [...current]
            const lastIndex = updated.length - 1
            if (lastIndex >= 0 && updated[lastIndex]?.deepResearch) {
              const done = status.phases_completed ?? []
              const prev = updated[lastIndex].deepResearch!
              updated[lastIndex] = {
                ...updated[lastIndex],
                meta:
                  status.status === "completed"
                    ? "Hoàn thành"
                    : "Đang xử lý...",
                deepResearch: {
                  ...prev,
                  status:
                    status.status === "completed" ? "completed" : "in_progress",
                  sessionId,
                  phasesCompleted: done,
                  currentPhase:
                    status.status === "completed"
                      ? null
                      : (status.current_phase ??
                        (done.includes("build") ? "write" : "build")),
                  currentStage:
                    status.status === "completed"
                      ? null
                      : (status.current_stage ??
                        (done.includes("build") ? "write_start" : "research")),
                  activities: mergeActivities(
                    prev.activities,
                    status.activities
                  ),
                  message:
                    status.status === "completed"
                      ? "Hoàn thành báo cáo."
                      : (status.message ??
                        (done.includes("build")
                          ? "Đang viết báo cáo..."
                          : "Đang xây dựng tri thức...")),
                },
              }
            }
            return updated
          })

          if (status.status === "completed") return
          await new Promise((resolve) => setTimeout(resolve, 10000))
        }
      }

      let reportConversationId: string | undefined

      const streamClassificationFallback = async (conversationId?: string) => {
        const fallbackInstruction = `The user tried to start a deep financial research report, but their request could not be classified as a specific company, industry, sector, or macroeconomic topic.

Answer conversationally in the user's language. Explain that deep research needs a clearer research target, ask what they want to search about, and give a few examples such as a company, an industry/sector, or a macroeconomic topic. If the message is a greeting or casual chat, respond naturally and invite them to provide a research topic when ready.`
        let streamedText = ""
        let fallbackConversationId: string | undefined = conversationId

        await streamChatResponse(
          {
            message: topic,
            conversationId: conversationId ?? session.id,
            modelName: selectedModel,
            systemInstruction: fallbackInstruction,
            persistUserMessage: false,
          },
          {
            onConversationId: (nextConversationId) => {
              fallbackConversationId = nextConversationId
            },
            onChunk: (chunk) => {
              streamedText += chunk
              onTranscriptChange((current) => {
                const updated = [...current]
                const lastIndex = updated.length - 1
                if (
                  lastIndex >= 0 &&
                  updated[lastIndex]?.role === "assistant"
                ) {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    body: streamedText,
                    meta: "",
                    deepResearch: undefined,
                  }
                }
                return updated
              })
            },
            onDone: ({ conversationId: nextConversationId }) => {
              fallbackConversationId = nextConversationId
            },
          }
        )

        onTranscriptChange((current) => {
          const updated = [...current]
          const lastIndex = updated.length - 1
          if (lastIndex >= 0 && updated[lastIndex]?.role === "assistant") {
            updated[lastIndex] = {
              ...updated[lastIndex],
              body:
                streamedText.trim() ||
                "I need a clearer research topic before I can start deep research.",
              meta: "",
              deepResearch: undefined,
            }
          }
          return updated
        })

        if (fallbackConversationId && fallbackConversationId !== session.id) {
          onSessionChange?.(fallbackConversationId)
        }
      }

      try {
        await streamReportGeneration(
          {
            topic,
            stream: true,
            conversation_id: session.id ?? null,
            model_name: selectedModel,
            template_content: researchPlan?.templateContent,
            max_section_subqueries:
              researchPlan?.researchOptions?.maxSectionSubqueries,
            max_follow_up_queries:
              researchPlan?.researchOptions?.maxFollowUpQueries,
            max_search_results: researchPlan?.researchOptions?.maxSearchResults,
          },
          {
            onDisconnected: (sessionId) => {
              void pollReportStatus(sessionId)
            },
            onStarted: (sessionId, startedPhases, conversationId) => {
              reportConversationId = conversationId
              if (
                session.id &&
                conversationId &&
                conversationId !== session.id
              ) {
                onSessionChange?.(conversationId)
              }
              void pollReportStatus(sessionId)
              onTranscriptChange((current) => {
                const updated = [...current]
                const lastIndex = updated.length - 1
                if (lastIndex >= 0 && updated[lastIndex]?.deepResearch) {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    deepResearch: {
                      ...updated[lastIndex].deepResearch!,
                      status: "in_progress",
                      sessionId,
                      phases: startedPhases,
                      currentPhase: startedPhases[0],
                      currentStage: "classify",
                      activities: updated[lastIndex].deepResearch!.activities
                        .length
                        ? updated[lastIndex].deepResearch!.activities
                        : [
                            {
                              id: `activity-${++activityIdCounter}`,
                              type: "info",
                              message: "Đang phân loại chủ đề...",
                              timestamp: Date.now(),
                            },
                          ],
                      message: "Đang phân loại chủ đề...",
                    },
                  }
                }
                return updated
              })
            },
            onProgress: (event, serverActivity) => {
              onTranscriptChange((current) => {
                const updated = [...current]
                const lastIndex = updated.length - 1
                if (lastIndex >= 0 && updated[lastIndex]?.deepResearch) {
                  const prev = updated[lastIndex].deepResearch!
                  const timestamp = Date.now()
                  const newActivity: ResearchActivity = serverActivity ?? {
                    id: `activity-${++activityIdCounter}`,
                    type: (event.type as ResearchActivity["type"]) ?? "info",
                    message: event.message,
                    timestamp,
                    stage: event.stage,
                    phase: event.phase,
                    query: event.query,
                    results: event.results,
                    ticker: event.ticker,
                    count: event.count,
                    section: event.section,
                    filename: event.filename,
                  }

                  let newPhase = prev.currentPhase
                  if (event.phase === "build") {
                    newPhase = "build"
                  } else if (event.phase === "write") {
                    newPhase = "write"
                  }

                  const newPhasesCompleted = [...prev.phasesCompleted]
                  if (
                    event.stage === "build_complete" &&
                    !newPhasesCompleted.includes("build")
                  ) {
                    newPhasesCompleted.push("build")
                  }

                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    deepResearch: {
                      ...prev,
                      currentPhase: newPhase,
                      currentStage: event.stage,
                      phasesCompleted: newPhasesCompleted,
                      activities: appendActivity(prev.activities, newActivity),
                      message: event.message,
                    },
                  }
                }
                return updated
              })
            },
            onCompleted: (sessionId, _outputFiles, message, conversationId) => {
              reportConversationId = conversationId ?? reportConversationId
              onTranscriptChange((current) => {
                const updated = [...current]
                const lastIndex = updated.length - 1
                if (lastIndex >= 0 && updated[lastIndex]?.deepResearch) {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    body: message,
                    meta: "Hoàn thành",
                    deepResearch: {
                      ...updated[lastIndex].deepResearch!,
                      status: "completed",
                      sessionId,
                      currentPhase: null,
                      currentStage: null,
                      phasesCompleted: updated[lastIndex].deepResearch!.phases,
                      message,
                    },
                  }
                }
                return updated
              })
              if (reportConversationId && reportConversationId !== session.id) {
                onSessionChange?.(reportConversationId)
              }
            },
            onError: (sessionId, error, message, conversationId) => {
              reportConversationId = conversationId ?? reportConversationId
              if (error.includes("Cannot classify topic")) {
                void streamClassificationFallback(reportConversationId)
                return
              }

              onTranscriptChange((current) => {
                const updated = [...current]
                const lastIndex = updated.length - 1
                if (lastIndex >= 0 && updated[lastIndex]?.deepResearch) {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    body: `Nghiên cứu sâu thất bại: ${message}`,
                    meta: "Lỗi",
                    deepResearch: {
                      ...updated[lastIndex].deepResearch!,
                      status: "failed",
                      sessionId,
                      currentPhase: null,
                      currentStage: null,
                      message,
                    },
                  }
                }
                return updated
              })
              if (reportConversationId && reportConversationId !== session.id) {
                onSessionChange?.(reportConversationId)
              }
            },
          }
        )
      } catch (error) {
        onTranscriptChange((current) => {
          const updated = [...current]
          const lastIndex = updated.length - 1
          if (lastIndex >= 0 && updated[lastIndex]?.deepResearch) {
            updated[lastIndex] = {
              ...updated[lastIndex],
              body: `Nghiên cứu sâu thất bại: ${error instanceof Error ? error.message : "Unknown error"}`,
              meta: "Lỗi",
              deepResearch: {
                ...updated[lastIndex].deepResearch!,
                status: "failed",
                message:
                  error instanceof Error ? error.message : "Unknown error",
              },
            }
          }
          return updated
        })
      }
    },
    [onSessionChange, onTranscriptChange, selectedModel, session.id]
  )

  const handleResearchPlanChange = useCallback(
    (topic: string, nextPlan: ResearchPlan) => {
      onTranscriptChange((current) =>
        current.map((message) =>
          message.researchPlan?.topic === topic
            ? { ...message, researchPlan: nextPlan }
            : message
        )
      )
    },
    [onTranscriptChange]
  )

  const handleStartResearch = useCallback(
    async (topic: string) => {
      if (isSubmitting) {
        return
      }

      let selectedResearchPlan: ResearchPlan | undefined

      onTranscriptChange((current) => {
        const updated = [...current]
        const planIndex = [...updated]
          .reverse()
          .findIndex(
            (message) =>
              message.role === "assistant" &&
              message.researchPlan?.awaitingConfirmation &&
              message.researchPlan.topic === topic
          )

        if (planIndex === -1) {
          return current
        }

        const actualIndex = updated.length - 1 - planIndex
        selectedResearchPlan = updated[actualIndex].researchPlan
        updated.splice(actualIndex, 1)
        return updated
      })

      setIsSubmitting(true)
      try {
        await handleDeepResearch(topic, {
          appendUserMessage: false,
          researchPlan: selectedResearchPlan,
        })
      } finally {
        setIsSubmitting(false)
        onConversationUpdated?.()
      }
    },
    [
      handleDeepResearch,
      isSubmitting,
      onConversationUpdated,
      onTranscriptChange,
    ]
  )

  const handleSubmit = useCallback(
    async (retryMessage?: string) => {
      const trimmedDraft = retryMessage ?? draft.trim()
      if (!trimmedDraft || isSubmitting) {
        return
      }

      if (session.mode === "deep") {
        const userMessage = createUserMessage(trimmedDraft, "deep")
        userMessage.title = "Nghiên cứu sâu"

        const pendingAssistantMessage: TranscriptMessage = {
          role: "assistant",
          mode: "deep",
          label: "DeepFishy",
          title: "Đang chuẩn bị kế hoạch",
          body: "Đang chuẩn bị kế hoạch nghiên cứu...",
          meta: "Đang xử lý...",
          isLoading: true,
        }

        const pendingTranscript = [
          ...transcript,
          userMessage,
          pendingAssistantMessage,
        ]

        onTranscriptChange(pendingTranscript)
        setDraft("")
        setIsSubmitting(true)

        try {
          const result = await generateReport({
            topic: trimmedDraft,
            conversation_id: session.id,
            classify_only: true,
            model_name: selectedModel,
          })

          const resolvedAssistantMessage =
            result.action === "plan"
              ? createResearchPlanMessage(result.topic, {
                  templateKind: result.template_kind,
                  templateContent: result.template_content,
                  researchOptions: result.research_options
                    ? {
                        maxSectionSubqueries:
                          result.research_options.max_section_subqueries,
                        maxFollowUpQueries:
                          result.research_options.max_follow_up_queries,
                        maxSearchResults: result.research_options.max_search_results,
                      }
                    : undefined,
                })
              : createAssistantMessage(result.message, "deep")

          const nextTranscript = [
            ...transcript,
            userMessage,
            resolvedAssistantMessage,
          ]

          if (result.conversation_id && result.conversation_id !== session.id) {
            onSessionChange?.(result.conversation_id, nextTranscript)
          }

          onTranscriptChange(nextTranscript)
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Unknown error"
          onTranscriptChange([
            ...transcript,
            userMessage,
            createAssistantMessage(`Request failed: ${message}`, "deep"),
          ])
        } finally {
          setIsSubmitting(false)
          onConversationUpdated?.()
        }
        return
      }

      if (!retryMessage) {
        const userMessage = createUserMessage(trimmedDraft, session.mode)
        onTranscriptChange((current) => [...current, userMessage])
      }
      setDraft("")
      setIsSubmitting(true)
      let hasAssistantMessage = !!retryMessage
      let streamedConversationId: string | undefined

      try {
        let streamedText = ""
        await streamChatResponse(
          {
            message: trimmedDraft,
            conversationId: session.id,
            modelName: selectedModel,
          },
          {
            onConversationId: (conversationId) => {
              streamedConversationId = conversationId
            },
            onChunk: (chunk) => {
              streamedText += chunk
              onTranscriptChange((current) => {
                if (!hasAssistantMessage) {
                  hasAssistantMessage = true
                  return [
                    ...current,
                    createAssistantMessage(streamedText, session.mode),
                  ]
                }

                const updated = [...current]
                const lastIndex = updated.length - 1
                if (lastIndex < 0 || updated[lastIndex]?.role !== "assistant") {
                  return [
                    ...current,
                    createAssistantMessage(streamedText, session.mode),
                  ]
                }

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  body: streamedText,
                }
                return updated
              })
            },
            onDone: ({ conversationId }) => {
              streamedConversationId = conversationId
            },
          }
        )

        onTranscriptChange((current) => {
          if (!hasAssistantMessage) {
            return current
          }

          const updated = [...current]
          const lastIndex = updated.length - 1
          if (lastIndex < 0 || updated[lastIndex]?.role !== "assistant") {
            return current
          }

          updated[lastIndex] = {
            ...updated[lastIndex],
            body: streamedText.trim() || "I couldn't generate a response.",
          }
          return updated
        })

        if (streamedConversationId && streamedConversationId !== session.id) {
          onSessionChange?.(streamedConversationId)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error"

        onTranscriptChange((current) => {
          if (!hasAssistantMessage) {
            return [
              ...current,
              createAssistantMessage(
                `Request failed: ${message}`,
                session.mode
              ),
            ]
          }

          const updated = [...current]
          const lastIndex = updated.length - 1
          if (lastIndex < 0 || updated[lastIndex]?.role !== "assistant") {
            return [
              ...current,
              createAssistantMessage(
                `Request failed: ${message}`,
                session.mode
              ),
            ]
          }

          updated[lastIndex] = {
            ...updated[lastIndex],
            body: `Request failed: ${message}`,
          }
          return updated
        })
      } finally {
        setIsSubmitting(false)
        onConversationUpdated?.()
      }
    },
    [
      draft,
      isSubmitting,
      onConversationUpdated,
      onSessionChange,
      onTranscriptChange,
      selectedModel,
      session.id,
      session.mode,
      transcript,
    ]
  )

  const handleRetry = useCallback(() => {
    const lastUserMessage = [...transcript]
      .reverse()
      .find((m) => m.role === "user")

    if (lastUserMessage) {
      onTranscriptChange((current) => {
        const updated = [...current]
        if (
          updated.length > 0 &&
          updated[updated.length - 1]?.role === "assistant" &&
          updated[updated.length - 1]?.body.startsWith("Request failed:")
        ) {
          updated.pop()
        }
        return updated
      })
      void handleSubmit(lastUserMessage.body)
    }
  }, [transcript, onTranscriptChange, handleSubmit])

  const lastMessage = transcript[transcript.length - 1]
  const isError =
    lastMessage?.role === "assistant" &&
    lastMessage.body.startsWith("Request failed:")
  return (
    <section
      className={cn(
        "flex min-h-0 overflow-hidden rounded-xl border border-slate-200/80 bg-gradient-to-b from-white/95 to-slate-50/80 shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)] backdrop-blur-md",
        className
      )}
    >
      <div
        className={cn(
          "flex h-full min-w-0 flex-1 flex-col bg-[linear-gradient(180deg,#ffffff,#f8fafc)]",
          isNewSession ? "justify-center" : ""
        )}
      >
        <ScrollArea
          className={cn(
            "min-h-0 flex-1 px-4 py-4 xl:px-6 xl:py-5",
            isNewSession ? "hidden" : ""
          )}
        >
          <div className="mx-auto flex w-full max-w-4xl min-w-0 flex-col gap-3 overflow-x-hidden xl:gap-5">
            {transcript.map((message, index) => (
              <div
                key={`${session.id}-${index}-${message.title}`}
                className="min-w-0"
                style={{
                  opacity: 0,
                  animation: "fadeInUp 0.3s ease forwards",
                  animationDelay: `${Math.min(index * 50, 200)}ms`,
                }}
              >
                {message.deepResearch ? (
                  <div className="flex min-w-0 justify-start overflow-hidden">
                    <div className="flex w-full max-w-[95%] min-w-0 flex-col gap-1 xl:max-w-[min(80%,48rem)]">
                      <div className="flex items-center gap-2 px-1 text-[0.7rem] font-medium text-slate-500">
                        <Avatar className="size-5 rounded-md">
                          <AvatarFallback className="rounded-md bg-gradient-to-br from-indigo-500 to-violet-600">
                            <Fish className="size-3 text-white" />
                          </AvatarFallback>
                        </Avatar>
                        <span>{message.label}</span>
                      </div>
                      <DeepResearchProgress
                        {...message.deepResearch}
                        onOpenReport={onOpenReport}
                      />
                    </div>
                  </div>
                ) : (
                  <TranscriptCard
                    {...message}
                    onStartResearch={handleStartResearch}
                    onResearchPlanChange={handleResearchPlanChange}
                    isStartingResearch={isSubmitting}
                  />
                )}
              </div>
            ))}
            <div ref={bottomAnchorRef} />
          </div>
        </ScrollArea>

        {isError && !isSubmitting && (
          <div className="flex justify-center px-4 pb-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleRetry}
              className="rounded-full border-indigo-200 bg-indigo-50 px-4 text-indigo-700 hover:bg-indigo-100"
            >
              <RefreshCw data-icon="inline-start" />
              Thử lại
            </Button>
          </div>
        )}

        <div
          className={cn(
            "bg-transparent px-4 xl:px-6",
            isNewSession ? "py-4 xl:py-5" : "pb-4 xl:pb-5"
          )}
        >
          <div className="mx-auto flex max-w-4xl flex-col gap-3 xl:gap-4">
            {isNewSession ? (
              <div className="mb-4 flex flex-col items-center gap-4 text-center">
                <div className="relative">
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 opacity-20 blur-xl" />
                  <Avatar className="size-14 rounded-2xl shadow-[0_8px_24px_rgba(79,70,229,0.35)]">
                    <AvatarFallback className="rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600">
                      <Fish className="size-7 stroke-[2.5] text-white" />
                    </AvatarFallback>
                  </Avatar>
                </div>
                <div>
                  <h1 className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-2xl font-bold tracking-tight text-transparent">
                    DeepFishy
                  </h1>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Trợ lý nghiên cứu tài chính AI cho thị trường Việt Nam
                  </p>
                </div>
              </div>
            ) : null}

            <Card className="group relative gap-0 rounded-2xl border-slate-200/80 bg-white py-0 shadow-[0_4px_20px_-2px_rgba(79,70,229,0.06)] transition-all duration-300 focus-within:border-indigo-300 focus-within:shadow-[0_4px_24px_-2px_rgba(79,70,229,0.12)]">
              <CardContent className="px-4 py-3 xl:px-5 xl:py-4">
                <div className="flex w-full items-start">
                  <Textarea
                    ref={textareaRef}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault()
                        void handleSubmit()
                      }
                    }}
                    rows={1}
                    className="max-h-24 min-h-[28px] flex-1 resize-none overflow-y-auto border-0 px-0 py-0 text-sm leading-7 text-slate-900 shadow-none ring-0 placeholder:text-slate-400 focus-visible:border-0 focus-visible:ring-0 xl:max-h-32 xl:min-h-[32px] xl:text-base xl:leading-8"
                    placeholder={
                      session.mode === "deep"
                        ? "Nhập chủ đề nghiên cứu sâu..."
                        : session.inputPlaceholder
                    }
                  />
                </div>

                <div className="flex w-full items-center justify-between gap-2 pt-2 xl:gap-3">
                  <div className="flex items-center gap-1.5 xl:gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        onModeChange?.(
                          session.mode === "deep" ? "normal" : "deep"
                        )
                      }
                      className={cn(
                        "rounded-full border px-2.5 text-xs backdrop-blur-sm duration-200 xl:px-3.5 xl:text-sm",
                        session.mode === "deep"
                          ? "border-indigo-200 bg-gradient-to-r from-indigo-50 to-violet-50 text-indigo-700 shadow-[0_2px_8px_rgba(79,70,229,0.15)]"
                          : "border-slate-200/80 bg-slate-50 text-slate-500 hover:border-slate-300 hover:bg-slate-100 hover:text-slate-700"
                      )}
                    >
                      <Globe
                        data-icon="inline-start"
                        className={cn(
                          "transition-transform duration-300",
                          session.mode === "deep" && "rotate-[360deg]"
                        )}
                      />
                      <span className="hidden sm:inline">Nghiên cứu sâu</span>
                      <span className="sm:hidden">Sâu</span>
                      {session.mode === "deep" ? (
                        <X data-icon="inline-end" className="opacity-60" />
                      ) : null}
                    </Button>
                  </div>

                  <Button
                    type="button"
                    size="icon-lg"
                    onClick={() => void handleSubmit()}
                    disabled={isSubmitting || !draft.trim()}
                    className="rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-[0_4px_14px_0_rgba(79,70,229,0.3)] transition-transform duration-200 hover:-translate-y-0.5 disabled:opacity-40 disabled:hover:translate-y-0"
                  >
                    {isSubmitting ? <Spinner /> : <ArrowUp strokeWidth={2.5} />}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </section>
  )
}
