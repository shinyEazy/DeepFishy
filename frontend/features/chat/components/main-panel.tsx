"use client"

import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react"
import { ArrowUp, Globe, LoaderCircle, X } from "lucide-react"

import { streamChatResponse } from "@/features/chat/api/responses"
import { TranscriptCard } from "@/features/chat/components/transcript-card"
import {
  createAssistantMessage,
  createUserMessage,
} from "@/features/chat/lib/messages"
import type {
  Mode,
  SessionContent,
  TranscriptMessage,
} from "@/features/chat/types"
import { cn } from "@/lib/utils"

export function ChatMainPanel({
  className,
  session,
  transcript,
  onTranscriptChange,
  onModeChange,
  onSessionChange,
  onConversationUpdated,
}: {
  className?: string
  session: SessionContent
  transcript: TranscriptMessage[]
  onTranscriptChange: Dispatch<SetStateAction<TranscriptMessage[]>>
  onModeChange?: Dispatch<SetStateAction<Mode>>
  onSessionChange?: (sessionId: string) => void
  onConversationUpdated?: () => void
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

  const handleSubmit = async () => {
    const trimmedDraft = draft.trim()
    if (!trimmedDraft || isSubmitting) {
      return
    }

    const userMessage = createUserMessage(trimmedDraft, session.mode)

    onTranscriptChange((current) => [...current, userMessage])
    setDraft("")
    setIsSubmitting(true)
    let hasAssistantMessage = false
    let streamedConversationId: string | undefined

    try {
      let streamedText = ""
      await streamChatResponse(
        {
          message: trimmedDraft,
          conversationId: session.id,
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
      const message =
        error instanceof Error ? error.message : "Unknown request error"

      onTranscriptChange((current) => {
        if (!hasAssistantMessage) {
          return [
            ...current,
            createAssistantMessage(`Request failed: ${message}`, session.mode),
          ]
        }

        const updated = [...current]
        const lastIndex = updated.length - 1
        if (lastIndex < 0 || updated[lastIndex]?.role !== "assistant") {
          return [
            ...current,
            createAssistantMessage(`Request failed: ${message}`, session.mode),
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
  }

  return (
    <section
      className={cn(
        "min-h-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)]",
        className
      )}
    >
      <div
        className={cn(
          "flex h-full min-h-0 flex-col bg-[linear-gradient(180deg,#ffffff,#f8fafc)]",
          isNewSession ? "justify-center" : ""
        )}
      >
        <div
          className={cn(
            "min-h-0 flex-1 overflow-y-auto px-6 py-5",
            isNewSession ? "hidden" : ""
          )}
        >
          <div className="mx-auto flex max-w-4xl flex-col gap-4">
            {transcript.map((message, index) => (
              <TranscriptCard
                key={`${session.id}-${index}-${message.title}`}
                {...message}
              />
            ))}
            <div ref={bottomAnchorRef} />
          </div>
        </div>

        <div
          className={cn(
            "bg-transparent px-6",
            isNewSession ? "py-5" : "pb-5"
          )}
        >
          <div className="mx-auto flex max-w-4xl flex-col gap-4">
            <div className="flex w-full flex-col gap-3 rounded-[1.75rem] border border-slate-200 bg-white px-5 py-4 shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)] transition-all duration-300">
              <div className="flex w-full items-start">
                <textarea
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
                  className="max-h-32 min-h-[32px] flex-1 resize-none overflow-y-auto bg-transparent text-base leading-8 text-slate-900 outline-none placeholder:text-slate-500"
                  placeholder={session.inputPlaceholder}
                />
              </div>

              <div className="flex w-full items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      onModeChange?.(
                        session.mode === "deep" ? "normal" : "deep"
                      )
                    }
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium backdrop-blur-sm transition-all",
                      session.mode === "deep"
                        ? "border-blue-200 bg-blue-50 text-blue-700 shadow-[0_6px_18px_-8px_rgba(37,99,235,0.5)] hover:border-blue-300 hover:bg-blue-100"
                        : "border-slate-200/80 bg-slate-100/70 text-slate-500 hover:border-slate-300 hover:bg-slate-100 hover:text-slate-700"
                    )}
                  >
                    <Globe className="size-4" />
                    <span>Deep Research</span>
                    {session.mode === "deep" ? <X className="size-4" /> : null}
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => void handleSubmit()}
                  disabled={isSubmitting || !draft.trim()}
                  className="hero-button flex size-8 shrink-0 items-center justify-center rounded-full text-white transition-all duration-200 hover:-translate-y-0.5"
                >
                  {isSubmitting ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <ArrowUp className="size-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
