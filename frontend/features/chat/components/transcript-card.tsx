import {
  ArrowDown,
  ArrowUp,
  ChartNoAxesColumn,
  Clock3,
  FileSearch,
  Fish,
  Plus,
  SearchCheck,
  Settings2,
  Trash2,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type { ResearchPlan, TranscriptMessage } from "@/features/chat/types"
import { cn } from "@/lib/utils"

type TemplateSection = {
  id: string
  heading: string
  content: string
  level: 1 | 2 | 3
  editable: boolean
}

function clampNumber(value: number, min: number, max: number) {
  return Math.max(min, Math.min(value, max))
}

function createSectionId(index: number) {
  return `template-section-${index}-${Date.now()}`
}

function isEditableTemplateHeading(heading: string, level: 1 | 2 | 3) {
  return level === 2 && /^\d+\.\s+/.test(heading.trim())
}

function parseTemplateSections(markdown: string): TemplateSection[] {
  const lines = markdown.split("\n")
  const sections: TemplateSection[] = []
  let current: TemplateSection | null = null
  let preface: string[] = []

  const flushCurrent = () => {
    if (!current) return
    sections.push({ ...current, content: current.content.trim() })
    current = null
  }

  lines.forEach((line) => {
    const match = /^(#{1,3})\s+(.+)$/.exec(line)
    if (!match) {
      if (current) {
        current.content = `${current.content}${current.content ? "\n" : ""}${line}`
      } else if (line.trim()) {
        preface.push(line)
      }
      return
    }

    if (preface.length) {
      sections.push({
        id: createSectionId(sections.length + 1),
        heading: "Tổng quan",
        content: preface.join("\n").trim(),
        level: 2,
        editable: false,
      })
      preface = []
    }

    flushCurrent()
    const level = Math.min(match[1].length, 3) as 1 | 2 | 3
    const heading = match[2].trim()
    current = {
      id: createSectionId(sections.length + 1),
      heading,
      content: "",
      level,
      editable: isEditableTemplateHeading(heading, level),
    }
  })

  flushCurrent()

  if (preface.length) {
    sections.push({
      id: createSectionId(sections.length + 1),
      heading: "Tổng quan",
      content: preface.join("\n").trim(),
      level: 2,
      editable: false,
    })
  }

  return sections.length
    ? sections
    : [
        {
          id: createSectionId(1),
          heading: "1. Phần mới",
          content: "",
          level: 2,
          editable: true,
        },
      ]
}

function serializeTemplateSections(sections: TemplateSection[]) {
  return sections
    .filter((section) => section.heading.trim() || section.content.trim())
    .map((section) => {
      const heading = section.heading.trim() || "Phần chưa đặt tên"
      const prefix = "#".repeat(section.level || 2)
      const content = section.content.trim()
      return content ? `${prefix} ${heading}\n\n${content}` : `${prefix} ${heading}`
    })
    .join("\n\n")
}

export function TranscriptCard({
  role,
  body,
  label,
  meta,
  researchPlan,
  isLoading,
  onStartResearch,
  onResearchPlanChange,
  isStartingResearch = false,
}: TranscriptMessage & {
  onStartResearch?: (topic: string) => void
  onResearchPlanChange?: (topic: string, plan: ResearchPlan) => void
  isStartingResearch?: boolean
}) {
  const isAssistant = role === "assistant"
  const updateResearchPlan = (nextPlan: ResearchPlan) => {
    onResearchPlanChange?.(nextPlan.topic, nextPlan)
  }
  const updateResearchOption = (
    key: keyof NonNullable<ResearchPlan["researchOptions"]>,
    value: string,
    min: number,
    max: number
  ) => {
    if (!researchPlan?.researchOptions) {
      return
    }

    updateResearchPlan({
      ...researchPlan,
      researchOptions: {
        ...researchPlan.researchOptions,
        [key]: clampNumber(Number(value) || min, min, max),
      },
    })
  }
  const templateSections = researchPlan?.templateContent
    ? parseTemplateSections(researchPlan.templateContent)
    : []
  const editableTemplateSections = templateSections.filter(
    (section) => section.editable
  )
  const updateTemplateSections = (sections: TemplateSection[]) => {
    if (!researchPlan) {
      return
    }

    updateResearchPlan({
      ...researchPlan,
      templateContent: serializeTemplateSections(sections),
    })
  }
  const updateTemplateSection = (
    sectionId: string,
    changes: Partial<Pick<TemplateSection, "heading" | "content">>
  ) => {
    updateTemplateSections(
      templateSections.map((section) =>
        section.id === sectionId ? { ...section, ...changes } : section
      )
    )
  }
  const addTemplateSection = () => {
    const nextNumber = editableTemplateSections.length + 1
    updateTemplateSections([
      ...templateSections,
      {
        id: createSectionId(templateSections.length + 1),
        heading: `${nextNumber}. Phần mới`,
        content: "",
        level: 2,
        editable: true,
      },
    ])
  }
  const removeTemplateSection = (sectionId: string) => {
    if (editableTemplateSections.length <= 1) {
      return
    }
    updateTemplateSections(
      templateSections.filter((section) => section.id !== sectionId)
    )
  }
  const moveTemplateSection = (sectionId: string, direction: -1 | 1) => {
    const editableIndex = editableTemplateSections.findIndex(
      (section) => section.id === sectionId
    )
    const nextEditable = editableTemplateSections[editableIndex + direction]
    if (!nextEditable) {
      return
    }

    const nextSections = [...templateSections]
    const index = nextSections.findIndex((section) => section.id === sectionId)
    const nextIndex = nextSections.findIndex(
      (section) => section.id === nextEditable.id
    )
    if (index < 0 || nextIndex < 0) {
      return
    }

    const [section] = nextSections.splice(index, 1)
    nextSections.splice(nextIndex, 0, section)
    updateTemplateSections(nextSections)
  }

  return (
    <div
      className={cn(
        "flex w-full",
        isAssistant ? "justify-start" : "justify-end"
      )}
    >
      <div
        className={cn(
          "flex max-w-[95%] flex-col gap-2 xl:max-w-[min(80%,48rem)]",
          isAssistant ? "items-start" : "items-end"
        )}
      >
        {/* Label row */}
        <div className="flex items-center gap-2 px-1 text-[0.7rem] font-medium text-slate-500">
          {isAssistant ? (
            <Avatar className="size-5 rounded-md">
              <AvatarFallback className="rounded-md bg-gradient-to-br from-indigo-500 to-violet-600">
                <Fish className="size-3 text-white" />
              </AvatarFallback>
            </Avatar>
          ) : null}
          <span>{label}</span>
          {!isAssistant && meta ? (
            <>
              <span className="text-slate-300">·</span>
              <span className="text-slate-300">{meta}</span>
            </>
          ) : null}
        </div>

        {/* Message card */}
        <div
          className={cn(
            "inline-flex max-w-full flex-col rounded-2xl border p-4 transition-all duration-300",
            isAssistant
              ? "border-slate-200/60 bg-white"
              : "border-transparent bg-gradient-to-br from-indigo-600 to-violet-600 text-white"
          )}
        >
          <div className="flex flex-col gap-3">
            {isAssistant ? (
              isLoading ? (
                <div className="flex items-center gap-3 text-sm text-slate-600">
                  <Spinner className="size-4 text-indigo-500" />
                  <span>{body}</span>
                </div>
              ) : (
                <>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ className, ...props }) => (
                        <h1
                          className={cn(
                            "text-lg font-bold tracking-tight text-slate-900",
                            className
                          )}
                          {...props}
                        />
                      ),
                      h2: ({ className, ...props }) => (
                        <h2
                          className={cn(
                            "text-base font-bold tracking-tight text-slate-900",
                            className
                          )}
                          {...props}
                        />
                      ),
                      h3: ({ className, ...props }) => (
                        <h3
                          className={cn(
                            "text-sm font-semibold text-slate-900",
                            className
                          )}
                          {...props}
                        />
                      ),
                      p: ({ className, ...props }) => (
                        <p
                          className={cn(
                            "text-sm leading-7 [overflow-wrap:break-word] [word-break:normal] text-slate-600",
                            className
                          )}
                          {...props}
                        />
                      ),
                      ul: ({ className, ...props }) => (
                        <ul
                          className={cn(
                            "list-disc space-y-1.5 pl-5 text-sm leading-7 text-slate-600",
                            className
                          )}
                          {...props}
                        />
                      ),
                      ol: ({ className, ...props }) => (
                        <ol
                          className={cn(
                            "list-decimal space-y-1.5 pl-5 text-sm leading-7 text-slate-600",
                            className
                          )}
                          {...props}
                        />
                      ),
                      li: ({ className, ...props }) => (
                        <li
                          className={cn(
                            "[overflow-wrap:break-word]",
                            className
                          )}
                          {...props}
                        />
                      ),
                      a: ({ className, ...props }) => (
                        <a
                          className={cn(
                            "font-medium text-indigo-600 underline underline-offset-2 transition-colors duration-200 hover:text-indigo-700",
                            className
                          )}
                          target="_blank"
                          rel="noreferrer"
                          {...props}
                        />
                      ),
                      blockquote: ({ className, ...props }) => (
                        <blockquote
                          className={cn(
                            "border-l-2 border-indigo-200 bg-indigo-50/50 pl-4 text-slate-500 italic",
                            className
                          )}
                          {...props}
                        />
                      ),
                      code: ({ className, children, ...props }) => {
                        const isInline = !String(className ?? "").includes(
                          "language-"
                        )

                        if (isInline) {
                          return (
                            <code
                              className={cn(
                                "rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-indigo-700",
                                className
                              )}
                              {...props}
                            >
                              {children}
                            </code>
                          )
                        }

                        return (
                          <code
                            className={cn("font-mono text-sm", className)}
                            {...props}
                          >
                            {children}
                          </code>
                        )
                      },
                      pre: ({ className, ...props }) => (
                        <pre
                          className={cn(
                            "overflow-x-auto rounded-xl bg-slate-950/95 p-4 text-sm leading-6 text-slate-100 shadow-inner",
                            className
                          )}
                          {...props}
                        />
                      ),
                      strong: ({ className, ...props }) => (
                        <strong
                          className={cn(
                            "font-semibold text-slate-900",
                            className
                          )}
                          {...props}
                        />
                      ),
                      table: ({ className, ...props }) => (
                        <div className="overflow-x-auto">
                          <table
                            className={cn(
                              "w-full border-collapse text-sm",
                              className
                            )}
                            {...props}
                          />
                        </div>
                      ),
                      th: ({ className, ...props }) => (
                        <th
                          className={cn(
                            "border-b border-slate-200 px-3 py-2 text-left font-semibold text-slate-700",
                            className
                          )}
                          {...props}
                        />
                      ),
                      td: ({ className, ...props }) => (
                        <td
                          className={cn(
                            "border-b border-slate-100 px-3 py-2 text-slate-600",
                            className
                          )}
                          {...props}
                        />
                      ),
                      hr: ({ className, ...props }) => (
                        <hr
                          className={cn("my-3 border-slate-100", className)}
                          {...props}
                        />
                      ),
                    }}
                  >
                    {body}
                  </ReactMarkdown>

                  {researchPlan ? (
                    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-slate-50 shadow-none">
                      <CardHeader>
                        <CardTitle className="text-lg leading-tight font-semibold text-slate-900">
                          Kế hoạch nghiên cứu
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="">
                        <div className="flex flex-col py-1">
                          {[
                            ...researchPlan.steps,
                            researchPlan.readyMessage,
                          ].map((step, index, steps) => {
                            const Icon =
                              index === 0
                                ? SearchCheck
                                : index === 1
                                  ? ChartNoAxesColumn
                                  : index === 2
                                    ? FileSearch
                                    : Clock3

                            return (
                              <div
                                key={step}
                                className="flex items-start gap-3 text-sm text-slate-700"
                              >
                                <div className="flex w-5 shrink-0 flex-col items-center">
                                  <Icon className="size-4 text-slate-700" />
                                  {index < steps.length - 1 ? (
                                    <div className="my-2 h-4 w-px bg-slate-300" />
                                  ) : null}
                                </div>
                                <div className="min-w-0 pb-5 font-medium text-slate-900 last:pb-0">
                                  {step}
                                </div>
                              </div>
                            )
                          })}
                        </div>

                        {researchPlan.templateContent ? (
                          <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-white p-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 space-y-1">
                                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                                  <Settings2 className="size-4 text-slate-500" />
                                  <span>Cấu trúc báo cáo</span>
                                </div>
                                <p className="text-xs leading-5 text-slate-500">
                                  Đây là các phần sẽ được dùng để tạo báo cáo. Bạn có thể chỉnh tiêu đề, nội dung cần phân tích hoặc thêm phần mới trước khi bắt đầu.
                                </p>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={addTemplateSection}
                                className="shrink-0 rounded-full border-slate-200 text-xs"
                              >
                                <Plus data-icon="inline-start" />
                                Thêm phần
                              </Button>
                            </div>

                            <div className="space-y-3">
                              {editableTemplateSections.map((section, index) => (
                                <div
                                  key={section.id}
                                  className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3"
                                >
                                  <div className="mb-3 flex items-center justify-between gap-2">
                                    <span className="rounded-full bg-white px-2.5 py-1 text-[0.68rem] font-semibold text-slate-500 ring-1 ring-slate-200">
                                      Phần {index + 1}
                                    </span>
                                    <div className="flex items-center gap-1">
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon-sm"
                                        onClick={() =>
                                          moveTemplateSection(section.id, -1)
                                        }
                                        disabled={index === 0}
                                        className="size-7 rounded-full text-slate-500"
                                      >
                                        <ArrowUp className="size-3.5" />
                                      </Button>
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon-sm"
                                        onClick={() =>
                                          moveTemplateSection(section.id, 1)
                                        }
                                        disabled={index === editableTemplateSections.length - 1}
                                        className="size-7 rounded-full text-slate-500"
                                      >
                                        <ArrowDown className="size-3.5" />
                                      </Button>
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon-sm"
                                        onClick={() =>
                                          removeTemplateSection(section.id)
                                        }
                                        disabled={editableTemplateSections.length <= 1}
                                        className="size-7 rounded-full text-rose-500 hover:bg-rose-50 hover:text-rose-600"
                                      >
                                        <Trash2 className="size-3.5" />
                                      </Button>
                                    </div>
                                  </div>

                                  <div className="space-y-2.5">
                                    <label className="space-y-1.5 text-xs font-medium text-slate-600">
                                      <span>Tiêu đề phần</span>
                                      <Input
                                        value={section.heading}
                                        onChange={(event) =>
                                          updateTemplateSection(section.id, {
                                            heading: event.target.value,
                                          })
                                        }
                                        placeholder="Ví dụ: Tổng quan doanh nghiệp"
                                        className="rounded-xl border-slate-200 bg-white"
                                      />
                                    </label>
                                    <label className="space-y-1.5 text-xs font-medium text-slate-600">
                                      <span>Nội dung cần phân tích</span>
                                      <Textarea
                                        value={section.content}
                                        onChange={(event) =>
                                          updateTemplateSection(section.id, {
                                            content: event.target.value,
                                          })
                                        }
                                        placeholder="Mô tả các ý chính, câu hỏi nghiên cứu hoặc dữ liệu cần có trong phần này..."
                                        className="min-h-28 resize-y rounded-xl border-slate-200 bg-white text-xs leading-5 text-slate-700"
                                      />
                                    </label>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        {researchPlan.researchOptions ? (
                          <div className="mt-3 space-y-3 rounded-2xl border border-slate-200 bg-white p-3">
                            <div>
                              <div className="text-sm font-semibold text-slate-900">
                                Mức độ nghiên cứu
                              </div>
                              <p className="mt-1 text-xs leading-5 text-slate-500">
                                Tăng các giá trị này nếu bạn muốn báo cáo tìm sâu hơn, nhưng thời gian tạo báo cáo cũng có thể lâu hơn.
                              </p>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-3">
                              <label className="space-y-1.5 text-xs font-medium text-slate-600">
                                <span>Độ chi tiết mỗi phần</span>
                                <Input
                                  type="number"
                                  min={1}
                                  max={10}
                                  value={
                                    researchPlan.researchOptions
                                      .maxSectionSubqueries
                                  }
                                  onChange={(event) =>
                                    updateResearchOption(
                                      "maxSectionSubqueries",
                                      event.target.value,
                                      1,
                                      10
                                    )
                                  }
                                />
                                <span className="block text-[0.68rem] leading-4 font-normal text-slate-400">
                                  Càng cao thì mỗi phần được chia nhỏ để tìm kỹ hơn.
                                </span>
                              </label>
                              <label className="space-y-1.5 text-xs font-medium text-slate-600">
                                <span>Lượt tìm bổ sung</span>
                                <Input
                                  type="number"
                                  min={0}
                                  max={5}
                                  value={
                                    researchPlan.researchOptions
                                      .maxFollowUpQueries
                                  }
                                  onChange={(event) =>
                                    updateResearchOption(
                                      "maxFollowUpQueries",
                                      event.target.value,
                                      0,
                                      5
                                    )
                                  }
                                />
                                <span className="block text-[0.68rem] leading-4 font-normal text-slate-400">
                                  Số lần tìm thêm nếu dữ liệu ban đầu chưa đủ.
                                </span>
                              </label>
                              <label className="space-y-1.5 text-xs font-medium text-slate-600">
                                <span>Số nguồn mỗi lượt tìm</span>
                                <Input
                                  type="number"
                                  min={1}
                                  max={10}
                                  value={
                                    researchPlan.researchOptions.maxSearchResults
                                  }
                                  onChange={(event) =>
                                    updateResearchOption(
                                      "maxSearchResults",
                                      event.target.value,
                                      1,
                                      10
                                    )
                                  }
                                />
                                <span className="block text-[0.68rem] leading-4 font-normal text-slate-400">
                                  Số nguồn tham khảo lấy về cho mỗi lượt tìm.
                                </span>
                              </label>
                            </div>
                          </div>
                        ) : null}

                        {researchPlan.awaitingConfirmation &&
                        onStartResearch ? (
                          <div className="mt-4 flex justify-end">
                            <Button
                              type="button"
                              onClick={() =>
                                onStartResearch(researchPlan.topic)
                              }
                              disabled={isStartingResearch}
                              className="rounded-full px-5"
                            >
                              {isStartingResearch
                                ? "Đang bắt đầu..."
                                : (researchPlan.startLabel ??
                                  "Bắt đầu nghiên cứu")}
                            </Button>
                          </div>
                        ) : null}
                      </CardContent>
                    </Card>
                  ) : null}
                </>
              )
            ) : (
              <p className="text-sm leading-7 [overflow-wrap:break-word] [word-break:normal] text-white/90">
                {body}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
