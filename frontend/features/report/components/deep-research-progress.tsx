"use client"

import { useEffect, useMemo, useRef } from "react"
import {
  BarChart3,
  BookOpen,
  CheckCircle2,
  Database,
  ExternalLink,
  FileCheck,
  FileText,
  Globe,
  LoaderCircle,
  Search,
  Sparkles,
  Zap,
} from "lucide-react"

import type {
  ReportPhase,
  ReportStatus,
  ResearchActivity,
} from "@/features/report/types"
import { Button } from "@/components/ui/button"
import { ThinkingProcessSection } from "@/features/report/components/thinking-process-section"
import { cn } from "@/lib/utils"

// ─── Type config ────────────────────────────────────────────────────────────

type ActivityType = ResearchActivity["type"]

const ACTIVITY_CONFIG: Record<
  ActivityType,
  {
    label: string
    icon: React.ReactNode
    color: string
    bg: string
    border: string
    colorDot: string
  }
> = {
  web: {
    label: "Web",
    icon: <Globe className="size-3.5 stroke-2" />,
    color: "text-sky-600",
    bg: "bg-sky-50",
    border: "border-sky-200",
    colorDot: "bg-sky-500",
  },
  local: {
    label: "Local",
    icon: <Database className="size-3.5 stroke-2" />,
    color: "text-violet-600",
    bg: "bg-violet-50",
    border: "border-violet-200",
    colorDot: "bg-violet-500",
  },
  finance: {
    label: "Finance",
    icon: <BarChart3 className="size-3.5 stroke-2" />,
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    colorDot: "bg-emerald-500",
  },
  facts: {
    label: "KG",
    icon: <FileCheck className="size-3.5 stroke-2" />,
    color: "text-amber-600",
    bg: "bg-amber-50",
    border: "border-amber-200",
    colorDot: "bg-amber-500",
  },
  output: {
    label: "Output",
    icon: <FileText className="size-3.5 stroke-2" />,
    color: "text-indigo-600",
    bg: "bg-indigo-50",
    border: "border-indigo-200",
    colorDot: "bg-indigo-500",
  },
  info: {
    label: "Step",
    icon: <Sparkles className="size-3.5 stroke-2" />,
    color: "text-slate-500",
    bg: "bg-slate-50",
    border: "border-slate-200",
    colorDot: "bg-slate-400",
  },
}

const STAT_TYPES: ActivityType[] = [
  "web",
  "local",
  "finance",
  "facts",
  "output",
]

function phaseLabel(phase: ReportPhase) {
  return phase === "build" ? "Xây dựng tri thức" : "Viết báo cáo"
}

function phaseDesc(phase: ReportPhase) {
  return phase === "build"
    ? "Thu thập dữ liệu & kiến thức"
    : "Soạn thảo báo cáo cuối"
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ReportStatus }) {
  if (status === "in_progress") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
        <LoaderCircle className="size-3 animate-spin" />
        Đang chạy
      </span>
    )
  }
  if (status === "completed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-3 py-1 text-[11px] font-semibold text-emerald-100">
        <CheckCircle2 className="size-3" />
        Hoàn thành
      </span>
    )
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/20 px-3 py-1 text-[11px] font-semibold text-red-200">
        Lỗi
      </span>
    )
  }
  return null
}

function PhaseStep({
  phase,
  index,
  total,
  status: phaseStatus,
}: {
  phase: ReportPhase
  index: number
  total: number
  status: "pending" | "active" | "completed"
}) {
  const isLast = index === total - 1

  return (
    <div className="flex min-w-0 flex-1 flex-col items-center gap-2">
      {/* Node + connector line */}
      <div className="flex w-full items-center">
        {/* Left line */}
        {index > 0 && (
          <div
            className={cn(
              "h-0.5 flex-1 transition-all duration-500",
              phaseStatus === "completed" || phaseStatus === "active"
                ? "bg-gradient-to-r from-emerald-400 to-indigo-400"
                : "bg-slate-200"
            )}
          />
        )}

        {/* Step node */}
        <div className="relative shrink-0">
          {phaseStatus === "active" && (
            <div className="absolute inset-0 animate-ping rounded-full bg-indigo-400 opacity-30" />
          )}
          <div
            className={cn(
              "relative flex size-9 items-center justify-center rounded-full border-2 transition-all duration-500",
              phaseStatus === "completed"
                ? "border-emerald-400 bg-emerald-400 text-white shadow-[0_0_0_4px_rgba(52,211,153,0.15)]"
                : phaseStatus === "active"
                  ? "border-indigo-500 bg-indigo-500 text-white shadow-[0_0_0_4px_rgba(99,102,241,0.2)]"
                  : "border-slate-200 bg-white text-slate-300"
            )}
          >
            {phaseStatus === "completed" ? (
              <CheckCircle2 className="size-4 stroke-[2.5]" />
            ) : phaseStatus === "active" ? (
              <LoaderCircle className="size-4 animate-spin stroke-[2.5]" />
            ) : (
              <span className="text-xs font-bold">{index + 1}</span>
            )}
          </div>
        </div>

        {/* Right line */}
        {!isLast && (
          <div
            className={cn(
              "h-0.5 flex-1 transition-all duration-500",
              phaseStatus === "completed"
                ? "bg-gradient-to-r from-emerald-400 to-slate-200"
                : "bg-slate-200"
            )}
          />
        )}
      </div>

      {/* Label */}
      <div className="text-center">
        <p
          className={cn(
            "text-xs font-semibold transition-colors duration-300",
            phaseStatus === "completed"
              ? "text-emerald-600"
              : phaseStatus === "active"
                ? "text-indigo-700"
                : "text-slate-400"
          )}
        >
          {phaseLabel(phase)}
        </p>
        <p
          className={cn(
            "mt-0.5 text-[10px] leading-4",
            phaseStatus === "pending" ? "text-slate-300" : "text-slate-400"
          )}
        >
          {phaseDesc(phase)}
        </p>
      </div>
    </div>
  )
}

function StatCard({ type, count }: { type: ActivityType; count: number }) {
  const cfg = ACTIVITY_CONFIG[type]
  const hasActivity = count > 0

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-1.5 rounded-xl border p-3 transition-all duration-300",
        hasActivity
          ? `${cfg.bg} ${cfg.border} shadow-sm`
          : "border-slate-100 bg-slate-50/50"
      )}
    >
      <div
        className={cn(
          "flex size-7 items-center justify-center rounded-lg transition-all duration-300",
          hasActivity ? `${cfg.bg} ${cfg.color}` : "bg-slate-100 text-slate-300"
        )}
      >
        {cfg.icon}
      </div>
      <p
        className={cn(
          "text-base leading-none font-bold transition-colors duration-300",
          hasActivity ? cfg.color : "text-slate-300"
        )}
      >
        {count}
      </p>
      <p className="text-[9px] font-bold tracking-widest text-slate-400 uppercase">
        {cfg.label}
      </p>
    </div>
  )
}

function ActivityItem({ activity }: { activity: ResearchActivity }) {
  const cfg = ACTIVITY_CONFIG[activity.type] ?? ACTIVITY_CONFIG.info

  return (
    <div className="group flex min-w-0 items-start gap-3">
      {/* Color-coded left dot */}
      <div className="mt-1.5 flex shrink-0 flex-col items-center">
        <div className={cn("size-2 rounded-full", cfg.colorDot)} />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-bold tracking-wider uppercase",
              cfg.bg,
              cfg.color
            )}
          >
            {cfg.icon}
            {cfg.label}
          </span>
        </div>
        <p className="mt-1 text-xs leading-5 break-words text-slate-600">
          {activity.message}
        </p>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function DeepResearchProgress({
  status,
  topic,
  phases,
  currentPhase,
  currentStage,
  phasesCompleted,
  sessionId,
  message,
  activities,
  onOpenReport,
}: {
  status: ReportStatus
  topic: string
  phases: ReportPhase[]
  currentPhase: ReportPhase | null
  currentStage: string | null
  phasesCompleted: ReportPhase[]
  sessionId: string | null
  message: string | null
  activities: ResearchActivity[]
  onOpenReport?: (sessionId: string) => void
}) {
  const activitiesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (activitiesRef.current) {
      activitiesRef.current.scrollTop = activitiesRef.current.scrollHeight
    }
  }, [activities])

  const stageLabels: Record<string, string> = {
    classify: "Đang hiểu yêu cầu",
    build: "Đang xây dựng tri thức",
    plan: "Đang lập kế hoạch nghiên cứu",
    research: "Đang tìm kiếm và đọc nguồn",
    facts: "Đang lưu bằng chứng vào KG",
    output: "Đang tạo tài liệu trung gian",
    build_complete: "Đã hoàn tất xây dựng tri thức",
    write: "Đang viết báo cáo",
    write_start: "Đang khởi tạo Writer",
  }

  const latestActivity = activities.at(-1)

  const displayMessage = useMemo(() => {
    if (latestActivity && currentStage !== "classify") {
      return latestActivity.message
    }
    return (
      message ?? latestActivity?.message ?? "Đang chuẩn bị nghiên cứu sâu..."
    )
  }, [currentStage, latestActivity, message])

  const counts = useMemo(() => {
    return activities.reduce(
      (acc, activity) => {
        acc[activity.type] = (acc[activity.type] ?? 0) + 1
        return acc
      },
      {} as Partial<Record<ActivityType, number>>
    )
  }, [activities])

  const getPhaseStatus = (
    phase: ReportPhase
  ): "pending" | "active" | "completed" => {
    if (phasesCompleted.includes(phase)) return "completed"
    if (currentPhase === phase) return "active"
    return "pending"
  }

  const currentStageLabel = currentStage
    ? (stageLabels[currentStage] ?? currentStage)
    : "Đang chuẩn bị"

  // Reverse so newest is on top
  const visibleActivities = [...activities].reverse().slice(0, 12)

  return (
    <div className="w-full min-w-0 space-y-4">
      <ThinkingProcessSection activities={activities} status={status} />

      {status === "completed" && sessionId && (
        <Button
          size="lg"
          onClick={() => onOpenReport?.(sessionId)}
          className="w-full gap-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3 font-bold text-white shadow-[0_4px_14px_0_rgba(79,70,229,0.35)] hover:-translate-y-0.5 hover:from-indigo-500 hover:to-violet-500"
        >
          Mở
        </Button>
      )}
    </div>
  )
}
