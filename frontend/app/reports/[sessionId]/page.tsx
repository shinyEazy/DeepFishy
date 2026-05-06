"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  ArrowLeft,
  Download,
  FileText,
  LoaderCircle,
} from "lucide-react"
import Link from "next/link"

export default function ReportViewerPage() {
  const params = useParams()
  const sessionId = params.sessionId as string
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadReport() {
      try {
        const response = await fetch(
          `/api/reports/${encodeURIComponent(sessionId)}/content`
        )
        if (!response.ok) {
          throw new Error("Report not found")
        }
        const data = await response.json()
        setContent(data.content)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report")
      } finally {
        setLoading(false)
      }
    }

    loadReport()
  }, [sessionId])

  return (
    <div
      className="min-h-screen"
      style={{
        background:
          "radial-gradient(circle at top right, rgba(99,102,241,0.10) 0%, transparent 28rem), radial-gradient(circle at 10% 0%, rgba(124,58,237,0.07) 0%, transparent 22rem), linear-gradient(180deg, #f8fafc, #f1f5f9)",
      }}
    >
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm text-slate-600 transition-colors hover:text-slate-900"
          >
            <ArrowLeft className="size-4" />
            Quay lại
          </Link>
          <div className="flex-1">
            <h1 className="text-sm font-semibold text-slate-900">
              Báo cáo: {sessionId}
            </h1>
          </div>
          {content && (
            <button
              type="button"
              onClick={() => {
                const blob = new Blob([content], { type: "text/markdown" })
                const url = URL.createObjectURL(blob)
                const a = document.createElement("a")
                a.href = url
                a.download = `report-${sessionId}.md`
                a.click()
                URL.revokeObjectURL(url)
              }}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700"
            >
              <Download className="size-4" />
              Tải Markdown
            </button>
          )}
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-5xl px-4 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center gap-3 py-20">
            <LoaderCircle className="size-8 animate-spin text-indigo-500" />
            <p className="text-sm text-slate-500">Đang tải báo cáo...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center gap-3 py-20">
            <FileText className="size-12 text-slate-300" />
            <p className="text-sm text-slate-500">{error}</p>
            <Link
              href="/"
              className="mt-2 text-sm text-indigo-600 hover:text-indigo-700"
            >
              Quay về trang chủ
            </Link>
          </div>
        ) : content ? (
          <article className="prose prose-slate max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ className, ...props }) => (
                  <h1
                    className={cn(
                      "bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-3xl font-bold tracking-tight text-transparent",
                      className
                    )}
                    {...props}
                  />
                ),
                h2: ({ className, ...props }) => (
                  <h2
                    className={cn(
                      "mt-8 text-2xl font-bold tracking-tight text-slate-900",
                      className
                    )}
                    {...props}
                  />
                ),
                h3: ({ className, ...props }) => (
                  <h3
                    className={cn(
                      "mt-6 text-xl font-semibold text-slate-900",
                      className
                    )}
                    {...props}
                  />
                ),
                p: ({ className, ...props }) => (
                  <p
                    className={cn(
                      "text-base leading-7 text-slate-600",
                      className
                    )}
                    {...props}
                  />
                ),
                table: ({ className, ...props }) => (
                  <div className="overflow-x-auto">
                    <table
                      className={cn("w-full border-collapse", className)}
                      {...props}
                    />
                  </div>
                ),
                th: ({ className, ...props }) => (
                  <th
                    className={cn(
                      "border-b-2 border-slate-200 px-4 py-3 text-left font-semibold text-slate-700",
                      className
                    )}
                    {...props}
                  />
                ),
                td: ({ className, ...props }) => (
                  <td
                    className={cn(
                      "border-b border-slate-100 px-4 py-3 text-slate-600",
                      className
                    )}
                    {...props}
                  />
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </article>
        ) : null}
      </main>
    </div>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(" ")
}
