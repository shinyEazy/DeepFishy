type StreamEvent =
  | { type: "conversation_id"; conversation_id: string }
  | { type: "content"; content: string }
  | { type: "done"; conversation_id: string; message_id: string }
  | { type: "error"; error: string }

function parseErrorMessage(text: string): string {
  try {
    const parsed = JSON.parse(text)
    if (parsed.detail) return parsed.detail
    if (parsed.error?.message) return parsed.error.message
    if (parsed.message) return parsed.message
    if (typeof parsed.error === "string") return parsed.error
  } catch {
    // Not JSON, use raw text
  }
  return text || "Unknown error"
}

export async function streamChatResponse(
  request: {
    message: string
    conversationId?: string
    systemInstruction?: string
    persistUserMessage?: boolean
  },
  handlers: {
    onChunk: (chunk: string) => void
    onConversationId?: (conversationId: string) => void
    onDone?: (payload: { conversationId: string; messageId: string }) => void
    onError?: (message: string) => void
  }
) {
  const response = await fetch("/api/responses", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      message: request.message,
      conversation_id: request.conversationId,
      stream: true,
      system_instruction: request.systemInstruction,
      persist_user_message: request.persistUserMessage ?? true,
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(parseErrorMessage(errorText))
  }

  if (!response.body) {
    throw new Error("Streaming response body is not available.")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let lastError: string | null = null

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })

    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""

    for (const event of events) {
      const line = event
        .split("\n")
        .find((part) => part.trimStart().startsWith("data:"))

      if (!line) {
        continue
      }

      const payload = line.replace(/^data:\s*/, "")
      const parsed = JSON.parse(payload) as StreamEvent

      if (parsed.type === "conversation_id") {
        handlers.onConversationId?.(parsed.conversation_id)
        continue
      }

      if (parsed.type === "content") {
        handlers.onChunk(parsed.content)
        continue
      }

      if (parsed.type === "error") {
        // Don't throw - backend is retrying internally
        // Just track the error in case stream ends without success
        lastError = parsed.error
        continue
      }

      if (parsed.type === "done") {
        handlers.onDone?.({
          conversationId: parsed.conversation_id,
          messageId: parsed.message_id,
        })
        return
      }
    }

    if (done) {
      if (buffer.trim()) {
        const payload = buffer.replace(/^data:\s*/, "").trim()
        if (payload) {
          const parsed = JSON.parse(payload) as StreamEvent
          if (parsed.type === "conversation_id") {
            handlers.onConversationId?.(parsed.conversation_id)
          } else if (parsed.type === "content") {
            handlers.onChunk(parsed.content)
          } else if (parsed.type === "done") {
            handlers.onDone?.({
              conversationId: parsed.conversation_id,
              messageId: parsed.message_id,
            })
            return
          } else if (parsed.type === "error") {
            lastError = parsed.error
          }
        }
      }

      // Only throw if we had errors AND never got a done event
      if (lastError) {
        throw new Error(lastError)
      }
      return
    }
  }
}
