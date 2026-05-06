import { Download, FileText, PanelRightClose, Printer, X } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

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

export function ReportSidebarHeader({
  sessionId,
  title,
  content,
  onClose,
}: {
  sessionId: string
  title: string
  content: string | null
  onClose: () => void
}) {
  return (
    <header className="flex shrink-0 items-center gap-3 px-4 py-3">
      <Avatar className="size-10 rounded-2xl">
        <AvatarFallback className="rounded-2xl bg-slate-950 text-white">
          <FileText />
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-950">{title}</p>
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
  )
}
