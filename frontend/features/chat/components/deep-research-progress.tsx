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
  PanelRightOpen,
  Search,
  Sparkles,
  Zap,
} from "lucide-react"

import type {
  ReportPhase,
  ReportStatus,
  ResearchActivity,
} from "@/features/chat/types/report"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

// ─── Type config ────────────────────────────────────────────────────────────

type ActivityType = ResearchActivity["type"]

const ACTIVITY_CONFIG: Record<
  ActivityType,
  { label: string; icon: React.ReactNode; color: string; bg: string; border: string; colorDot: string }
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

const STAT_TYPES: ActivityType[] = ["web", "local", "finance", "facts", "output"]

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

function StatCard({
  type,
  count,
}: {
  type: ActivityType
  count: number
}) {
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
          "text-base font-bold leading-none transition-colors duration-300",
          hasActivity ? cfg.color : "text-slate-300"
        )}
      >
        {count}
      </p>
      <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">
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
              "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider",
              cfg.bg,
              cfg.color
            )}
          >
            {cfg.icon}
            {cfg.label}
          </span>
        </div>
        <p className="mt-1 break-words text-xs leading-5 text-slate-600">
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
    return message ?? latestActivity?.message ?? "Đang chuẩn bị nghiên cứu sâu..."
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

  const getPhaseStatus = (phase: ReportPhase): "pending" | "active" | "completed" => {
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
    <div className="w-full min-w-0 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_4px_24px_-4px_rgba(79,70,229,0.12)]">

      {/* ── Gradient header ─────────────────────────────────────────────── */}
      <div className="relative overflow-hidden bg-[image:linear-gradient(135deg,#4f46e5_0%,#7c3aed_60%,#6d28d9_100%)] p-5">
        {/* Decorative blobs */}
        <div className="absolute -right-8 -top-8 size-32 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-4 right-16 size-20 rounded-full bg-violet-300/20 blur-xl" />

        <div className="relative flex min-w-0 items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/15 backdrop-blur-sm ring-1 ring-white/25">
              <Search className="size-5 stroke-2 text-white" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-white">Nghiên cứu sâu</p>
              <p className="mt-0.5 line-clamp-1 text-xs text-indigo-200">{topic}</p>
            </div>
          </div>
          <StatusBadge status={status} />
        </div>

        {/* Phase stepper */}
        <div className="relative mt-5 flex items-start gap-0">
          {phases.map((phase, i) => (
            <PhaseStep
              key={phase}
              phase={phase}
              index={i}
              total={phases.length}
              status={getPhaseStatus(phase)}
            />
          ))}
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div className="space-y-4 p-4 sm:p-5">

        {/* Current stage indicator */}
        <div className="relative overflow-hidden rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50/60 to-violet-50/40 p-4">
          <div className="flex items-start gap-3">
            {/* Pulsing indicator dot */}
            <div className="relative mt-1 shrink-0">
              {status === "in_progress" && (
                <div className="absolute inset-0 animate-ping rounded-full bg-indigo-400 opacity-40" />
              )}
              <div
                className={cn(
                  "size-3 rounded-full",
                  status === "in_progress"
                    ? "bg-indigo-500"
                    : status === "completed"
                    ? "bg-emerald-500"
                    : "bg-slate-300"
                )}
              />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">
                Bước hiện tại
              </p>
              <p className="mt-1 text-sm font-bold text-slate-900">
                {currentStageLabel}
              </p>
              <p className="mt-1.5 break-words text-xs leading-5 text-slate-500">
                {displayMessage}
              </p>
            </div>
          </div>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-5 gap-2">
          {STAT_TYPES.map((type) => (
            <StatCard key={type} type={type} count={counts[type] ?? 0} />
          ))}
        </div>

        {/* Activity feed */}
        {activities.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-slate-100 bg-white">
            {/* Feed header */}
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/60 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <Zap className="size-3.5 stroke-2 text-indigo-500" />
                <p className="text-xs font-bold text-slate-700">Dòng hoạt động</p>
              </div>
              <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-600">
                {activities.length}
              </span>
            </div>

            {/* Scrollable timeline */}
            <div
              ref={activitiesRef}
              className="max-h-52 overflow-y-auto px-4 pt-3 pb-1 [scrollbar-width:thin] [scrollbar-color:#e2e8f0_transparent] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-200"
            >
              <div className="relative border-l-2 border-slate-100 pl-4">
                {visibleActivities.map((activity) => (
                  <ActivityItem key={activity.id} activity={activity} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Completion CTA */}
        {status === "completed" && sessionId && (
          <Button
            size="lg"
            onClick={() => onOpenReport?.(sessionId)}
            className="w-full gap-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3 font-bold text-white shadow-[0_4px_14px_0_rgba(79,70,229,0.35)] hover:-translate-y-0.5 hover:from-indigo-500 hover:to-violet-500"
          >
            <BookOpen className="size-4 stroke-2 transition-transform duration-200 group-hover/button:scale-110" />
            Xem báo cáo đầy đủ
            <ExternalLink className="size-3.5 stroke-2 opacity-70" />
          </Button>
        )}
      </div>
    </div>
  )
}
