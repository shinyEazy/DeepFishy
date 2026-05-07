import { ChevronDown } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { ChatModelOption } from "@/features/chat/lib/model-options"

export function ModelSelector({
  options,
  selectedModel,
  onModelChange,
}: {
  options: ChatModelOption[]
  selectedModel: string
  onModelChange: (model: string) => void
}) {
  const selectedOption =
    options.find((option) => option.id === selectedModel) ?? options[0]

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-700">Mô hình</span>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            className="h-9 w-full justify-between rounded-xl border-slate-200 bg-white px-3 text-sm font-medium text-slate-800 hover:bg-white hover:text-slate-900"
          >
            <span className="truncate">{selectedOption?.label}</span>
            <ChevronDown className="size-4 shrink-0 text-slate-400" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-(--radix-dropdown-menu-trigger-width)">
          <DropdownMenuRadioGroup
            value={selectedModel}
            onValueChange={onModelChange}
          >
            {options.map((option) => (
              <DropdownMenuRadioItem key={option.id} value={option.id}>
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{option.label}</span>
                  <span className="truncate text-xs text-slate-500">
                    {option.id}
                  </span>
                </div>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
