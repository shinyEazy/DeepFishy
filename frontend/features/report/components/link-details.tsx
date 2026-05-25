import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

function getDomain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

export function LinkDetails({
  href,
  children,
}: {
  href: string
  children: React.ReactNode
}) {
  const [isOpen, setIsOpen] = useState(false)
  const domain = getDomain(href)

  return (
    <span className="inline-flex max-w-full flex-col items-start align-baseline">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="link"
              size="xs"
              onClick={() => setIsOpen((value) => !value)}
              className="h-auto gap-1 p-0 font-medium text-indigo-700 underline underline-offset-3 hover:text-indigo-900"
            >
              <span>{children}</span>
              {isOpen ? (
                <ChevronUp className="size-3" />
              ) : (
                <ChevronDown className="size-3" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent sideOffset={6}>
            {isOpen ? "Thu gọn" : "Xem chi tiết liên kết"}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      {isOpen ? (
        <span className="mt-2 flex w-72 max-w-[min(36rem,calc(100vw-3rem))] min-w-0 flex-col gap-2 rounded-xl bg-slate-100 px-3 py-3 text-left text-xs text-slate-600">
          <span className="flex min-w-0 items-center gap-2">
            <Avatar className="size-5">
              <AvatarImage
                src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
                alt=""
              />
              <AvatarFallback className="text-[0.65rem] font-semibold">
                {domain.charAt(0).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <span className="shrink-0 font-semibold text-slate-950">
              {domain}
            </span>
          </span>
          <span className="break-all">{href}</span>
        </span>
      ) : null}
    </span>
  )
}
