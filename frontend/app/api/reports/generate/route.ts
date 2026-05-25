import { proxyBackendRequest } from "@/app/api/_lib/backend-proxy"

export async function POST(request: Request) {
  const body = await request.text()
  return proxyBackendRequest({
    path: "/api/reports/generate",
    method: "POST",
    body,
    headers: {
      "Content-Type": "application/json",
      Accept: request.headers.get("Accept") ?? "application/json",
    },
  })
}
