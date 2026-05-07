import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import type { ReportReference } from "@/features/report/lib/report-markdown"

export function ReferenceList({
  references,
  title = "Nguồn được dùng trong báo cáo",
}: {
  references: ReportReference[]
  title?: string
}) {
  const [isOpen, setIsOpen] = useState(false)

  if (references.length === 0) {
    return null
  }

  return (
    <section className="border-slate-200">
      <Button
        type="button"
        variant="ghost"
        onClick={() => setIsOpen((value) => !value)}
        className="inline-flex h-auto items-center gap-2 rounded-full bg-white px-4 py-2 text-xl font-semibold text-slate-950 transition-colors hover:bg-slate-100"
      >
        {title}
        {isOpen ? (
          <ChevronUp className="size-4" />
        ) : (
          <ChevronDown className="size-4" />
        )}
      </Button>

      <div
        className={`grid transition-[grid-template-rows,opacity,transform,margin] duration-300 ease-out ${
          isOpen
            ? "mt-2 translate-y-0 grid-rows-[1fr] opacity-100"
            : "mt-0 -translate-y-1 grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="flex min-h-0 flex-col gap-1 overflow-hidden pl-7">
          {references.map((reference) => (
            <a
              key={`${reference.id}-${reference.url}`}
              href={reference.url}
              target="_blank"
              rel="noreferrer"
              className="group flex min-w-0 items-center gap-2 rounded-full bg-slate-100 px-2.5 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-200 hover:text-slate-900"
            >
              <Avatar className="size-6">
                <AvatarImage
                  src={`https://www.google.com/s2/favicons?domain=${reference.domain}&sz=32`}
                  alt=""
                />
                <AvatarFallback className="text-[0.65rem] font-semibold">
                  {reference.domain.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <span className="shrink-0 font-semibold text-slate-900">
                {reference.domain}
              </span>
              <span className="min-w-0 truncate">{reference.title}</span>
            </a>
          ))}
        </div>
      </div>
    </section>
  )
}
