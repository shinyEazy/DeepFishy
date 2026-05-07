import { Plus } from "lucide-react"

import { Button } from "@/components/ui/button"

export function NewSessionButton({
  onCreateSession,
  onCloseMobile,
}: {
  onCreateSession?: () => void
  onCloseMobile?: () => void
}) {
  return (
    <Button
      type="button"
      variant="outline"
      onClick={() => {
        onCreateSession?.()
        onCloseMobile?.()
      }}
      className="h-auto w-full min-w-0 justify-start gap-2.5 rounded-xl border-indigo-100 bg-indigo-50/70 px-3 py-2.5 font-semibold text-indigo-700 hover:border-indigo-200 hover:bg-indigo-100 hover:text-indigo-700"
    >
      <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-white text-indigo-600 transition-colors duration-300">
        <Plus className="size-4 stroke-2" />
      </div>
      <span className="min-w-0 flex-1 truncate text-left">
        Cuộc trò chuyện mới
      </span>
    </Button>
  )
}
