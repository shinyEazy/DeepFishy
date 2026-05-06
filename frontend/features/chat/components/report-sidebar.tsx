"use client"

import { useEffect, useState } from "react"
import {
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  PanelRightClose,
  Printer,
  X,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { getReportContent } from "@/features/chat/api/reports"
import { cn } from "@/lib/utils"

function downloadMarkdown(sessionId: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `report-${sessionId}.md`
  anchor.click()
  URL.revokeObjectURL(url)
}

function downloadPdf() {
  window.print()
}

type ReportReference = {
  id: string
  title: string
  url: string
  domain: string
}

function getDomain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

function parseReportMarkdown(markdown: string): {
  body: string
  references: ReportReference[]
} {
  const headings = [...markdown.matchAll(/(^|\n)(#{1,6}\s*)?References\s*\n/gi)]
  const lastHeading = headings.at(-1)

  if (!lastHeading || lastHeading.index === undefined) {
    return { body: markdown, references: [] }
  }

  const headingStart = lastHeading.index + lastHeading[1].length
  const referencesStart = lastHeading.index + lastHeading[0].length
  const beforeReferences = markdown.slice(0, headingStart).trimEnd()
  const referencesBlock = markdown.slice(referencesStart).trim()

  if (!/\[\d+\]/.test(referencesBlock)) {
    return { body: markdown, references: [] }
  }

  const entries = [
    ...referencesBlock.matchAll(/\[(\d+)\]\s*([\s\S]*?)(?=\s*\[\d+\]\s*|$)/g),
  ]

  if (entries.length === 0) {
    return { body: markdown, references: [] }
  }

  const references = entries.flatMap((entry) => {
    const value = entry[2].trim()
    const markdownUrl = value.match(/\[[^\]]+\]\((https?:\/\/[^)]+)\)/)
    const rawUrl = markdownUrl?.[1] ?? value.match(/https?:\/\/\S+/)?.[0]

    if (!rawUrl) {
      return []
    }

    const url = rawUrl.replace(/[),.;]+$/, "")
    const titleEnd = markdownUrl?.index ?? value.indexOf(rawUrl)
    const title = value.slice(0, titleEnd).replace(/:\s*$/, "").trim()
    const domain = getDomain(url)

    return [
      {
        id: entry[1],
        title: title || domain,
        url,
        domain,
      },
    ]
  })

  if (references.length === 0) {
    return { body: markdown, references: [] }
  }

  return { body: beforeReferences, references }
}

function addCitationLinks(markdown: string) {
  return markdown.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_, ids: string) => {
    const normalizedIds = ids
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean)
      .join(",")

    return `[⌄](citation:${normalizedIds})`
  })
}

function CitationSources({
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
    <span className="ml-1 inline-flex max-w-full flex-col items-start align-baseline">
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
              className="inline-flex h-5 items-center rounded-full bg-slate-100 px-1.5 text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-950"
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

      {isOpen ? (
        <span className="mt-2 flex max-w-[min(36rem,calc(100vw-3rem))] flex-wrap gap-2">
          {sources.map((source) => (
            <span
              key={`${source.id}-${source.url}`}
              className="flex w-64 min-w-0 flex-col gap-2 rounded-xl bg-slate-100 px-3 py-3 text-left text-xs text-slate-600"
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
            </span>
          ))}
        </span>
      ) : null}
    </span>
  )
}

function ReferenceList({ references }: { references: ReportReference[] }) {
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

export function ReportSidebar({
  sessionId,
  title,
  isOpen,
  onClose,
}: {
  sessionId: string | null
  title: string
  isOpen: boolean
  onClose: () => void
}) {
  const [content, setContent] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen || !sessionId) {
      return
    }

    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) {
        setIsLoading(true)
        setError(null)
      }
    })

    getReportContent(sessionId)
      .then((report) => {
        if (!cancelled) {
          setContent(report.content)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Không thể tải báo cáo")
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, sessionId])

  if (!isOpen || !sessionId) {
    return null
  }

  const parsedContent = content ? parseReportMarkdown(content) : null
  const referencesById = new Map(
    parsedContent?.references.map((reference) => [reference.id, reference])
  )
  const renderedBody = parsedContent
    ? addCitationLinks(parsedContent.body)
    : null

  return (
    <aside className="report-sidebar fixed inset-y-0 right-0 z-50 flex h-full min-h-0 w-full max-w-2xl flex-col overflow-hidden border-l border-slate-200 bg-white shadow-[-24px_0_70px_rgba(15,23,42,0.16)] xl:relative xl:z-auto xl:max-w-none xl:rounded-xl xl:border xl:shadow-[0_4px_20px_-2px_rgba(79,70,229,0.10)]">
      <header className="flex shrink-0 items-center gap-3 px-4 py-3">
        <Avatar className="size-10 rounded-2xl">
          <AvatarFallback className="rounded-2xl bg-slate-950 text-white">
            <FileText />
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-950">
            {title}
          </p>
          <Badge variant="secondary" className="mt-1">
            Markdown report preview
          </Badge>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => content && downloadMarkdown(sessionId, content)}
          disabled={!content}
          className="text-xs"
        >
          <Download data-icon="inline-start" />
          MD
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={downloadPdf}
          disabled={!content}
          className="bg-slate-950 text-xs text-white hover:bg-indigo-700"
        >
          <Printer data-icon="inline-start" />
          PDF
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon-lg"
          onClick={onClose}
          className="rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          aria-label="Đóng báo cáo"
        >
          <X className="xl:hidden" />
          <PanelRightClose className="hidden xl:block" />
        </Button>
      </header>
      <Separator />

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-5 py-6">
          {isLoading ? (
            <div className="flex min-h-[calc(100svh-10rem)] flex-col items-center justify-center gap-3 text-slate-500">
              <Spinner className="size-7 text-indigo-500" />
              <p className="text-sm">Đang tải báo cáo...</p>
            </div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertTitle>Không thể tải báo cáo</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : parsedContent && renderedBody ? (
            <article
              id="report-print-root"
              className="report-markdown mx-auto max-w-none"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
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
                        "mt-8 border-t border-slate-200 pt-6 text-2xl font-bold text-slate-900",
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
                      className={cn(
                        "my-4 text-sm leading-7 text-slate-700",
                        className
                      )}
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
                  a: ({ className, href, children, ...props }) => {
                    if (href?.startsWith("citation:")) {
                      return (
                        <CitationSources
                          ids={href
                            .replace("citation:", "")
                            .split(",")
                            .filter(Boolean)}
                          references={referencesById}
                        />
                      )
                    }

                    return (
                      <a
                        href={href}
                        target={href?.startsWith("http") ? "_blank" : undefined}
                        rel={
                          href?.startsWith("http") ? "noreferrer" : undefined
                        }
                        className={cn(
                          "font-medium text-indigo-700 underline underline-offset-3 hover:text-indigo-900",
                          className
                        )}
                        {...props}
                      >
                        {children}
                      </a>
                    )
                  },
                }}
              >
                {renderedBody}
              </ReactMarkdown>
              <ReferenceList references={parsedContent.references} />
            </article>
          ) : null}
        </div>
      </ScrollArea>
    </aside>
  )
}
