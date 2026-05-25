import { proxyBackendRequest } from "@/app/api/_lib/backend-proxy"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params

  return proxyBackendRequest({
    path: `/api/reports/${encodeURIComponent(sessionId)}/pdf`,
    method: "GET",
    headers: {
      Accept: "application/pdf",
    },
  })
}
