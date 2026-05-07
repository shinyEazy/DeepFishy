import { useState } from "react"
import {
  Check,
  ChevronDown,
  Copy,
  FileText,
  Search,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function openPdf(sessionId: string) {
  window.open(
    `/api/reports/${encodeURIComponent(sessionId)}/pdf`,
    "_blank",
    "noopener,noreferrer"
  )
}

async function copyContent(content: string) {
  await navigator.clipboard.writeText(content)
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
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    if (!content) {
      return
    }

    await copyContent(content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <header className="flex shrink-0 items-center gap-3 px-4 py-3">
      <Search className="size-5 shrink-0 text-slate-950" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-950">{title}</p>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            size="sm"
            disabled={!content}
            className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-slate-100"
          >
            Chia sẻ và xuất
            <ChevronDown data-icon="inline-end" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem onSelect={() => openPdf(sessionId)}>
            <FileText className="size-4" />
            Xuất sang Tài liệu
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={handleCopy}>
            {copied ? (
              <Check className="size-4" />
            ) : (
              <Copy className="size-4" />
            )}
            Sao chép nội dung
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Button
        type="button"
        variant="ghost"
        size="icon-lg"
        onClick={onClose}
        className="rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-900"
      >
        <X className="xl" />
      </Button>
    </header>
  )
}
