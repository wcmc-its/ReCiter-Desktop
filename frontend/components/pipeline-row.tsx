// frontend/components/pipeline-row.tsx
"use client";

import Link from "next/link";

export type Phase = "queued" | "retrieving" | "matching" | "analyzing" | "scoring" | "complete" | "error";

const PHASE_COLORS: Record<Phase, string> = {
  queued: "text-gray-400",
  retrieving: "text-blue-500",
  matching: "text-purple-500",
  analyzing: "text-amber-500",
  scoring: "text-red-500",
  complete: "text-green-500",
  error: "text-red-600",
};

const PHASE_BG: Record<Phase, string> = {
  queued: "bg-gray-50",
  retrieving: "bg-blue-50/50",
  matching: "bg-purple-50/50",
  analyzing: "bg-amber-50/50",
  scoring: "bg-red-50/50",
  complete: "bg-white",
  error: "bg-red-50/50",
};

const PHASE_BORDER: Record<Phase, string> = {
  queued: "border-gray-200",
  retrieving: "border-blue-300",
  matching: "border-purple-300",
  analyzing: "border-amber-300",
  scoring: "border-red-300",
  complete: "border-gray-200",
  error: "border-red-300",
};

const PHASE_LABELS: Record<Phase, string> = {
  queued: "Queued",
  retrieving: "Retrieving from PubMed",
  matching: "Identifying target authors",
  analyzing: "Computing features",
  scoring: "Scoring",
  complete: "Complete",
  error: "Error",
};

export interface LogEntry {
  time: string;
  msg: string;
  type: "info" | "progress" | "error";
}

interface PipelineRowProps {
  personId: string;
  name: string;
  phase: Phase;
  articleCount: number | null;
  scoreMin?: number;
  scoreMax?: number;
  scoreMedian?: number;
  progress?: number;
  isBottleneck?: boolean;
  log?: LogEntry[];
  expanded?: boolean;
  onToggle?: () => void;
}

function MiniSparkline({ min, max, median }: { min: number; max: number; median?: number }) {
  const w = 64;
  const h = 16;
  const toX = (v: number) => (v / 100) * w;
  return (
    <svg width={w} height={h} className="block">
      <rect x={toX(min)} y={4} width={Math.max(toX(max) - toX(min), 2)} height={8} rx={2} className="fill-green-400/20" />
      {median !== undefined && (
        <line x1={toX(median)} y1={2} x2={toX(median)} y2={14} className="stroke-green-500" strokeWidth={2} strokeLinecap="round" />
      )}
    </svg>
  );
}

function Spinner({ className }: { className?: string }) {
  return (
    <span className={`inline-block w-3.5 h-3.5 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin ${className ?? ""}`} />
  );
}

function MiniProgress({ progress, phase }: { progress: number; phase: Phase }) {
  const barColor = ({
    retrieving: "bg-blue-500",
    matching: "bg-purple-500",
    analyzing: "bg-amber-500",
    scoring: "bg-red-500",
  } as Partial<Record<Phase, string>>)[phase] ?? "bg-gray-400";

  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1 rounded bg-gray-200 overflow-hidden">
        <div className={`h-full rounded ${barColor} transition-all duration-500`} style={{ width: `${progress * 100}%` }} />
      </div>
      <span className="text-xs text-gray-400 tabular-nums w-8 text-right">{Math.round(progress * 100)}%</span>
    </div>
  );
}

export function PipelineRow({
  personId,
  name,
  phase,
  articleCount,
  scoreMin,
  scoreMax,
  scoreMedian,
  progress,
  isBottleneck,
  log,
  expanded,
  onToggle,
}: PipelineRowProps) {
  const isActive = !["queued", "complete", "error"].includes(phase);
  const isClickable = isActive || (phase === "complete");

  return (
    <div className={`border rounded-lg overflow-hidden ${PHASE_BORDER[phase]} ${PHASE_BG[phase]} transition-colors`}>
      <div
        className={`grid grid-cols-[1.5fr_1fr_0.6fr_1.2fr_1fr] items-center px-5 py-3 ${isClickable ? "cursor-pointer hover:bg-gray-50/50" : ""}`}
        onClick={onToggle}
      >
        <span className={`text-sm font-medium ${phase === "complete" ? "text-gray-900" : isActive ? "text-gray-900" : "text-gray-500"}`}>
          {phase === "complete" ? (
            <Link href={`/results/${personId}`} className="hover:underline" onClick={(e) => e.stopPropagation()}>
              {name}
            </Link>
          ) : name}
        </span>
        <span className="text-xs font-mono text-gray-400">{personId}</span>
        <span className="text-sm text-gray-500 tabular-nums">{articleCount != null ? articleCount.toLocaleString() : "\u2014"}</span>
        <span className={`text-xs flex items-center gap-2 ${PHASE_COLORS[phase]}`}>
          {isActive && <Spinner />}
          {phase === "complete" && <span>✓</span>}
          {phase === "error" && <span>✕</span>}
          {PHASE_LABELS[phase]}
        </span>
        <div>
          {isActive && progress !== undefined && <MiniProgress progress={progress} phase={phase} />}
          {isBottleneck && <span className="text-xs text-amber-500 font-medium block">Taking longer than usual</span>}
          {phase === "complete" && scoreMin !== undefined && scoreMax !== undefined && (
            <div className="flex items-center gap-2">
              <MiniSparkline min={scoreMin} max={scoreMax} median={scoreMedian} />
              <span className="text-xs text-gray-400 tabular-nums">{scoreMin}–{scoreMax}</span>
            </div>
          )}
          {phase === "queued" && <span className="text-xs text-gray-400">—</span>}
        </div>
      </div>

      {/* Expanded activity log */}
      {expanded && log && log.length > 0 && (
        <div className="border-t border-gray-200 px-5 py-3 bg-gray-50/80">
          <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Activity Log</p>
          {log.map((entry, i) => (
            <div key={i} className="flex gap-3 py-0.5 text-xs">
              <span className="font-mono text-gray-400 shrink-0">{entry.time}</span>
              <span className={entry.type === "error" ? "text-red-500" : entry.type === "progress" ? "text-blue-500" : "text-gray-500"}>
                {entry.msg}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
