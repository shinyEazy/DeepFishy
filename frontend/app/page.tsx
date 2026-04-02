import { ChatWorkspace } from "@/features/chat/components/workspace"

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ session?: string }>
}) {
  const params = await searchParams

  return <ChatWorkspace activeSessionId={params.session} />
}
