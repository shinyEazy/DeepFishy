import { NextResponse } from "next/server"

const API_CANDIDATES = [
  process.env.DEEPFISHY_API_BASE_URL,
  process.env.NEXT_PUBLIC_API_BASE_URL,
  "http://127.0.0.1:1214",
  "http://localhost:1214",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
].filter((value): value is string => Boolean(value))

export async function POST(request: Request) {
  const body = await request.text()
  let lastError: string | null = null

  for (const baseUrl of API_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/responses/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: request.headers.get("Accept") ?? "application/json",
        },
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

      if (!response.ok) {
        return new NextResponse(responseText, {
          status: response.status,
          headers: {
            "Content-Type": contentType,
          },
        })
      }

      return new NextResponse(responseText, {
        status: 200,
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
        "Unable to reach the backend responses API. Start the FastAPI server or set DEEPFISHY_API_BASE_URL.",
      lastError,
      tried: API_CANDIDATES,
    },
    { status: 502 }
  )
}
