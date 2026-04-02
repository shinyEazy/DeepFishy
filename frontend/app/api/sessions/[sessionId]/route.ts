import { proxyBackendRequest } from "@/app/api/_lib/backend-proxy"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params

  return proxyBackendRequest({
    path: `/api/sessions/${encodeURIComponent(sessionId)}`,
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  })
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params

  return proxyBackendRequest({
    path: `/api/sessions/${encodeURIComponent(sessionId)}`,
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  })
}
