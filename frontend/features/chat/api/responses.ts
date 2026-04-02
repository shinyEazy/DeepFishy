type StreamEvent =
  | { type: "conversation_id"; conversation_id: string }
  | { type: "content"; content: string }
  | { type: "done"; conversation_id: string; message_id: string }
  | { type: "error"; error: string }

export async function streamChatResponse(
  request: {
    message: string
    conversationId?: string
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
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `Request failed with status ${response.status}`)
  }

  if (!response.body) {
    throw new Error("Streaming response body is not available.")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

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
        handlers.onError?.(parsed.error)
        throw new Error(parsed.error)
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
          } else if (parsed.type === "error") {
            handlers.onError?.(parsed.error)
            throw new Error(parsed.error)
          }
        }
      }
      return
    }
  }
}
