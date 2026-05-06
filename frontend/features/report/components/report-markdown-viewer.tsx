import ReactMarkdown, { defaultUrlTransform } from "react-markdown"
import remarkGfm from "remark-gfm"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CitationSources } from "@/features/report/components/citation-sources"
import { LinkDetails } from "@/features/report/components/link-details"
import { ReferenceList } from "@/features/report/components/reference-list"
import type { ReportReference } from "@/features/report/lib/report-markdown"
import { cn } from "@/lib/utils"

export function ReportMarkdownViewer({
  body,
  references,
}: {
  body: string
  references: ReportReference[]
}) {
  const referencesById = new Map(
    references.map((reference) => [reference.id, reference])
  )

  return (
    <article
      id="report-print-root"
      className="report-markdown mx-auto max-w-none"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) =>
          url.startsWith("citation:") ? url : defaultUrlTransform(url)
        }
        components={{
          h1: ({ className, ...props }) => (
            <h1
              className={cn(
                "mb-5 text-3xl font-bold tracking-tight text-slate-950",
                className
              )}
              {...props}
            />
          ),
          h2: ({ className, ...props }) => (
            <h2
              className={cn(
                "border-slate-200 text-2xl font-bold text-slate-900",
                className
              )}
              {...props}
            />
          ),
          h3: ({ className, ...props }) => (
            <h3
              className={cn(
                "mt-6 text-lg font-semibold text-slate-900",
                className
              )}
              {...props}
            />
          ),
          p: ({ className, ...props }) => (
            <p
              className={cn("my-4 text-sm leading-7 text-slate-700", className)}
              {...props}
            />
          ),
          ul: ({ className, ...props }) => (
            <ul
              className={cn(
                "my-4 list-disc space-y-2 pl-5 text-sm leading-7 text-slate-700",
                className
              )}
              {...props}
            />
          ),
          ol: ({ className, ...props }) => (
            <ol
              className={cn(
                "my-4 list-decimal space-y-2 pl-5 text-sm leading-7 text-slate-700",
                className
              )}
              {...props}
            />
          ),
          hr: () => null,
          table: ({ className, ...props }) => (
            <div className="my-5 rounded-xl border border-slate-200">
              <Table className={className} {...props} />
            </div>
          ),
          thead: ({ className, ...props }) => (
            <TableHeader className={className} {...props} />
          ),
          tbody: ({ className, ...props }) => (
            <TableBody className={className} {...props} />
          ),
          tr: ({ className, ...props }) => (
            <TableRow className={className} {...props} />
          ),
          th: ({ className, ...props }) => (
            <TableHead
              className={cn(
                "bg-slate-50 px-3 py-2 font-semibold text-slate-800",
                className
              )}
              {...props}
            />
          ),
          td: ({ className, ...props }) => (
            <TableCell
              className={cn(
                "px-3 py-2 align-top whitespace-normal text-slate-700",
                className
              )}
              {...props}
            />
          ),
          a: ({ href, children }) => {
            if (href?.startsWith("citation:")) {
              return (
                <CitationSources
                  ids={href.replace("citation:", "").split(",").filter(Boolean)}
                  references={referencesById}
                />
              )
            }

            if (href) {
              return <LinkDetails href={href}>{children}</LinkDetails>
            }

            return <span>{children}</span>
          },
        }}
      >
        {body}
      </ReactMarkdown>
      <ReferenceList references={references} />
    </article>
  )
}
