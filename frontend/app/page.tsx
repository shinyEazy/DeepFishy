import { ChatWorkspace } from "@/components/chat/workspace"

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ session?: string }>
}) {
  const params = await searchParams

  return <ChatWorkspace activeSessionId={params.session} />
}
