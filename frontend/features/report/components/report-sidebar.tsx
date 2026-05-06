import { useEffect, useMemo, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { getReportContent } from "@/features/report/api/reports"
import { ReportMarkdownViewer } from "@/features/report/components/report-markdown-viewer"
import { ReportSidebarHeader } from "@/features/report/components/report-sidebar-header"
import {
  addCitationLinks,
  parseReportMarkdown,
} from "@/features/report/lib/report-markdown"

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

  const parsedContent = useMemo(
    () => (content ? parseReportMarkdown(content) : null),
    [content]
  )
  const renderedBody = parsedContent
    ? addCitationLinks(parsedContent.body)
    : null

  if (!isOpen || !sessionId) {
    return null
  }

  return (
    <aside className="report-sidebar fixed inset-y-0 right-0 z-50 flex h-full min-h-0 w-full max-w-2xl flex-col overflow-hidden border-l border-slate-200 bg-white shadow-[-24px_0_70px_rgba(15,23,42,0.16)] xl:relative xl:z-auto xl:max-w-none xl:rounded-xl xl:border xl:shadow-[0_4px_20px_-2px_rgba(79,70,229,0.10)]">
      <ReportSidebarHeader
        sessionId={sessionId}
        title={title}
        content={content}
        onClose={onClose}
      />
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
            <ReportMarkdownViewer
              body={renderedBody}
              references={parsedContent.references}
            />
          ) : null}
        </div>
      </ScrollArea>
    </aside>
  )
}
