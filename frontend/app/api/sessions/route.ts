import { proxyBackendRequest } from "@/app/api/_lib/backend-proxy"

export async function GET(request: Request) {
  const url = new URL(request.url)

  return proxyBackendRequest({
    path: `/api/sessions/${url.search}`,
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  })
}

export async function POST(request: Request) {
  const body = await request.text()

  return proxyBackendRequest({
    path: "/api/sessions/",
    method: "POST",
    body,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  })
}
