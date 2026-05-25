import { useMemo, useState } from "react"
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Globe,
  LoaderCircle,
} from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ReportStatus, ResearchActivity } from "@/features/report/types"
import { cn } from "@/lib/utils"

const ACTIVITY_TITLES: Record<ResearchActivity["type"], string> = {
  web: "Tìm kiếm web",
  local: "Đối chiếu dữ liệu nội bộ",
  finance: "Phân tích chỉ số tài chính",
  classify: "Xác định yêu cầu",
  build: "Tổng hợp dữ liệu",
  plan: "Lập kế hoạch nghiên cứu",
  facts: "Tổng hợp bằng chứng",
  output: "Tổng hợp tài liệu",
  info: "Xác định yêu cầu",
  build_complete: "Hoàn thành tổng hợp dữ liệu",
  write: "Bắt đầu viết báo cáo",
  write_start: "Bắt đầu viết báo cáo",
}

function resultDomain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

function displayUrl(url: string) {
  try {
    const parsed = new URL(url)
    return `${parsed.hostname.replace(/^www\./, "")}${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return url.replace(/^https?:\/\/(www\.)?/, "")
  }
}

function ThinkingSearchResults({ activity }: { activity: ResearchActivity }) {
  if (!activity.results?.length) {
    return null
  }

  return (
    <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
      {activity.results.map((result) => {
        const domain = resultDomain(result.url)

        return (
          <a
            key={`${result.url}-${result.title}`}
            href={result.url}
            target="_blank"
            rel="noreferrer"
            className="group min-w-0 rounded-[20px] bg-slate-100 px-3 py-2.5 text-sm text-slate-700 transition-colors hover:bg-slate-200 hover:text-slate-900"
          >
            <div className="flex min-w-0 items-center gap-2">
              <Avatar className="size-5 shrink-0">
                <AvatarImage
                  src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
                  alt=""
                />
                <AvatarFallback className="text-[0.65rem] font-semibold">
                  {domain.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <span className="max-w-[4rem] shrink-0 truncate text-sm font-semibold text-slate-500">
                {displayUrl(result.url)}
              </span>
              <span className="min-w-0 truncate text-sm text-slate-900">
                {result.title}
              </span>
            </div>
          </a>
        )
      })}
    </div>
  )
}

function ThinkingActivity({
  activity,
  isLatest,
  status,
}: {
  activity: ResearchActivity
  isLatest: boolean
  status: ReportStatus
}) {
  const isWebActivity = activity.type === "web"
  const isActive = isLatest && status === "in_progress"

  if (isWebActivity) {
    return (
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex shrink-0 flex-col items-center self-stretch">
          <div className="mt-0.5 flex size-5 items-center justify-center rounded-full bg-white text-indigo-500 shadow-sm ring-1 ring-slate-200">
            {isActive ? (
              <LoaderCircle className="size-3.5 animate-spin" />
            ) : (
              <Globe className="size-3.5" />
            )}
          </div>
          <div className="my-2 w-px flex-1 bg-slate-300" />
        </div>
        <div className="min-w-0 flex-1 pb-4">
          <p className="text-sm font-bold text-slate-900">
            {activity.query
              ? `Tìm kiếm Web: "${activity.query}"`
              : "Tìm kiếm Web"}
          </p>
          <ThinkingSearchResults activity={activity} />
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-w-0 items-start gap-3">
      <div className="flex shrink-0 flex-col items-center self-stretch">
        <div className="flex size-5 items-center justify-center rounded-full bg-white text-slate-500 shadow-sm ring-1 ring-slate-200">
          {isActive ? (
            <LoaderCircle className="size-3.5 animate-spin text-indigo-500" />
          ) : (
            <CheckCircle2 className="size-3.5 text-indigo-500" />
          )}
        </div>
        <div className="my-2 w-px flex-1 bg-slate-300" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <p className="text-sm font-bold text-slate-900">
          {ACTIVITY_TITLES[activity.type] ?? activity.type}
        </p>
        <p className="text-sm leading-7 break-words text-slate-700 italic">
          {activity.message}
        </p>
      </div>
    </div>
  )
}

export function ThinkingProcessSection({
  activities,
  status,
  defaultOpen = true,
}: {
  activities: ResearchActivity[]
  status: ReportStatus
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const visibleActivities = useMemo(
    () => activities.slice(-16).sort((a, b) => a.timestamp - b.timestamp),
    [activities]
  )

  if (visibleActivities.length === 0) {
    return null
  }

  const latestActivityId = visibleActivities.at(-1)?.id

  return (
    <section className="border-slate-200">
      <Button
        type="button"
        variant="ghost"
        onClick={() => setIsOpen((value) => !value)}
        className="inline-flex h-auto items-center gap-2 rounded-full bg-white px-4 py-2 text-xl font-semibold text-slate-950 transition-colors hover:bg-slate-100"
      >
        Quá trình nghiên cứu
        {isOpen ? (
          <ChevronUp className="size-4" />
        ) : (
          <ChevronDown className="size-4" />
        )}
      </Button>

      <div
        className={cn(
          "grid transition-[grid-template-rows,opacity] duration-300 ease-out",
          isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        )}
      >
        <div className="min-h-0 overflow-hidden">
          <ScrollArea className="mt-3 h-[360px] rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="px-4 pt-4 pb-1">
              <div className="relative border-slate-100 pl-4">
                {visibleActivities.map((activity) => (
                  <ThinkingActivity
                    key={activity.id}
                    activity={activity}
                    isLatest={activity.id === latestActivityId}
                    status={status}
                  />
                ))}
              </div>
            </div>
          </ScrollArea>
        </div>
      </div>
    </section>
  )
}
