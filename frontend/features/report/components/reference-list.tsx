import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import type { ReportReference } from "@/features/report/lib/report-markdown"

export function ReferenceList({
  references,
}: {
  references: ReportReference[]
}) {
  if (references.length === 0) {
    return null
  }

  return (
    <section className="mt-10 border-t border-slate-200 pt-6">
      <h2 className="mb-4 text-2xl font-bold text-slate-900">References</h2>
      <div className="flex flex-col gap-2">
        {references.map((reference) => (
          <a
            key={`${reference.id}-${reference.url}`}
            href={reference.url}
            target="_blank"
            rel="noreferrer"
            className="group flex min-w-0 items-center gap-2 rounded-full bg-slate-100 px-2.5 py-1.5 text-sm text-slate-700 transition-colors hover:bg-indigo-50 hover:text-indigo-800"
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
            <span className="shrink-0 font-semibold text-slate-900 group-hover:text-indigo-900">
              {reference.domain}
            </span>
            <span className="min-w-0 truncate">{reference.title}</span>
          </a>
        ))}
      </div>
    </section>
  )
}
