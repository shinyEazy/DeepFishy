import { Badge } from "@/components/ui/badge"
import type { Mode } from "@/features/chat/types"

export function ModeBadge({
  mode,
  inverted = false,
}: {
  mode: Mode
  inverted?: boolean
}) {
  if (inverted) {
    return (
      <Badge
        variant="outline"
        className="rounded-full border-white/20 bg-white/10 px-2.5 text-white"
      >
        {mode === "deep" ? "Nghiên cứu sâu" : "Hỏi nhanh"}
      </Badge>
    )
  }

  return (
    <Badge
      variant={mode === "deep" ? "default" : "secondary"}
      className="rounded-full px-2.5 text-[0.72rem]"
    >
      {mode === "deep" ? "Nghiên cứu sâu" : "Hỏi nhanh"}
    </Badge>
  )
}
