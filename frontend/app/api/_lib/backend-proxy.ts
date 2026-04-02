import { NextResponse } from "next/server"

const API_CANDIDATES = [
  process.env.DEEPFISHY_API_BASE_URL,
  process.env.NEXT_PUBLIC_API_BASE_URL,
  "http://127.0.0.1:1214",
  "http://localhost:1214",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
].filter((value): value is string => Boolean(value))

export async function proxyBackendRequest({
  path,
  method,
  body,
  headers,
}: {
  path: string
  method: string
  body?: string
  headers?: HeadersInit
}) {
  let lastError: string | null = null

  for (const baseUrl of API_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
        method,
        headers,
        body,
        cache: "no-store",
      })
      const contentType = response.headers.get("Content-Type") ?? "application/json"

      if (contentType.includes("text/event-stream")) {
        return new NextResponse(response.body, {
          status: response.status,
          headers: {
            "Content-Type": contentType,
            "Cache-Control": "no-cache",
            Connection: "keep-alive",
          },
        })
      }

      const responseText = await response.text()
      return new NextResponse(responseText, {
        status: response.status,
        headers: {
          "Content-Type": contentType,
        },
      })
    } catch (error) {
      lastError = error instanceof Error ? error.message : "Unknown proxy error"
    }
  }

  return NextResponse.json(
    {
      detail:
        "Unable to reach the backend API. Start the FastAPI server or set DEEPFISHY_API_BASE_URL.",
      lastError,
      tried: API_CANDIDATES,
      path,
    },
    { status: 502 }
  )
}
