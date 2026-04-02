"use client"

import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react"
import { ArrowUp, LoaderCircle, Mic, Plus } from "lucide-react"

import { streamChatResponse } from "@/features/chat/api/responses"
import { TranscriptCard } from "@/features/chat/components/transcript-card"
import {
  buildConversationPayload,
  createAssistantMessage,
  createUserMessage,
} from "@/features/chat/lib/messages"
import type { SessionContent, TranscriptMessage } from "@/features/chat/types"
import { cn } from "@/lib/utils"

export function ChatMainPanel({
  className,
  session,
  transcript,
  onTranscriptChange,
}: {
  className?: string
  session: SessionContent
  transcript: TranscriptMessage[]
  onTranscriptChange: Dispatch<SetStateAction<TranscriptMessage[]>>
}) {
  const [draft, setDraft] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ block: "end" })
  }, [transcript, isSubmitting])

  const handleSubmit = async () => {
    const trimmedDraft = draft.trim()
    if (!trimmedDraft || isSubmitting) {
      return
    }

    const userMessage = createUserMessage(trimmedDraft, session.mode)
    const nextTranscript = [...transcript, userMessage]

    onTranscriptChange((current) => [...current, userMessage])
    setDraft("")
    setIsSubmitting(true)
    let hasAssistantMessage = false

    try {
      let streamedText = ""
      await streamChatResponse(
        JSON.stringify({
          ...buildConversationPayload(nextTranscript),
          stream: true,
        }),
        {
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
    }
  }

  return (
    <section
      className={cn(
        "min-h-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_4px_20px_-2px_rgba(79,70,229,0.1)]",
        className
      )}
    >
      <div className="flex h-full min-h-0 flex-col">
        <div
          className="min-h-0 flex-1 overflow-y-auto bg-[linear-gradient(180deg,#ffffff,#f8fafc)] px-6 py-5"
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
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault()
                      void handleSubmit()
                    }
                  }}
                  className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
                  placeholder={session.inputPlaceholder}
                />

                <button
                  type="button"
                  className="flex size-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition-all duration-200 hover:bg-slate-100 hover:text-indigo-600"
                >
                  <Mic className="size-4" />
                </button>

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
