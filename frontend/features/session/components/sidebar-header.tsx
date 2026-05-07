import { ChevronLeft, ChevronRight, Fish } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function SidebarHeader({
  collapsed,
  isMobile = false,
  onToggle,
  onCloseMobile,
}: {
  collapsed?: boolean
  isMobile?: boolean
  onToggle?: () => void
  onCloseMobile?: () => void
}) {
  return (
    <div className="flex shrink-0 items-center justify-between border-b border-slate-100/80 px-4 py-3.5 transition-all duration-300">
      <div
        className={cn(
          "flex items-center gap-2.5 overflow-hidden transition-all duration-300",
          collapsed && !isMobile ? "w-0 opacity-0" : "w-auto opacity-100"
        )}
      >
        <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-[0_2px_8px_rgba(79,70,229,0.25)]">
          <Fish className="size-4 stroke-[2.5] text-white" />
        </div>
        <h2 className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-sm font-bold tracking-tight whitespace-nowrap text-transparent">
          DeepFishy
        </h2>
      </div>
      <div
        className={cn(
          "flex items-center gap-1",
          collapsed && !isMobile && "w-full justify-center"
        )}
      >
        {isMobile ? (
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            onClick={onCloseMobile}
            className="text-slate-400 hover:bg-indigo-50 hover:text-indigo-700"
          >
            <ChevronLeft
              className={cn(
                "size-5 stroke-2 transition-transform duration-300"
              )}
            />
          </Button>
        ) : (
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            onClick={onToggle}
            className="text-slate-400 hover:bg-indigo-50 hover:text-indigo-700"
          >
            {collapsed ? (
              <ChevronRight className="size-5 stroke-2 transition-transform duration-300" />
            ) : (
              <ChevronLeft className="size-5 stroke-2 transition-transform duration-300" />
            )}
          </Button>
        )}
      </div>
    </div>
  )
}
