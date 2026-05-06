"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ReportReference } from "@/features/report/lib/report-markdown"

export function CitationSources({
  ids,
  references,
}: {
  ids: string[]
  references: Map<string, ReportReference>
}) {
  const [isOpen, setIsOpen] = useState(false)
  const sources = ids.flatMap((id) => {
    const reference = references.get(id)
    return reference ? [reference] : []
  })

  if (sources.length === 0) {
    return null
  }

  return (
    <span className="contents">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                setIsOpen((value) => !value)
              }}
              className="pointer-events-auto relative z-10 inline-flex size-6 items-center justify-center rounded-full bg-slate-100 text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-950"
              aria-expanded={isOpen}
              aria-label={isOpen ? "Thu gọn" : "Tìm hiểu thêm"}
            >
              {isOpen ? (
                <ChevronUp className="size-3" />
              ) : (
                <ChevronDown className="size-3" />
              )}
            </button>
          </TooltipTrigger>
          <TooltipContent sideOffset={6}>
            {isOpen ? "Thu gọn" : "Tìm hiểu thêm"}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <span
        className={`grid w-full transition-[grid-template-rows,opacity,transform,margin] duration-300 ease-out ${
          isOpen
            ? "mt-2 translate-y-0 grid-rows-[1fr] opacity-100"
            : "mt-0 -translate-y-1 grid-rows-[0fr] opacity-0"
        }`}
      >
        <span className="flex min-h-0 flex-wrap gap-2 overflow-hidden">
          {sources.map((source) => (
            <a
              key={`${source.id}-${source.url}`}
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="flex w-64 min-w-0 flex-col gap-2 rounded-xl bg-slate-100 px-3 py-3 text-left text-xs text-slate-600 transition-colors duration-200 hover:bg-slate-200 hover:text-slate-800"
            >
              <span className="line-clamp-2 font-semibold text-slate-950">
                {source.title}
              </span>
              <span className="flex min-w-0 items-center gap-2">
                <Avatar className="size-5">
                  <AvatarImage
                    src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
                    alt=""
                  />
                  <AvatarFallback className="text-[0.65rem] font-semibold">
                    {source.domain.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <span className="min-w-0 truncate">{source.url}</span>
              </span>
            </a>
          ))}
        </span>
      </span>
    </span>
  )
}
