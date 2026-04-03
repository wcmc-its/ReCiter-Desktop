// frontend/components/pipeline-row.tsx
"use client";

import Link from "next/link";
import { Progress } from "@/components/ui/progress";

export type Phase = "queued" | "retrieving" | "matching" | "analyzing" | "scoring" | "complete" | "error";

const PHASE_COLORS: Record<Phase, string> = {
  queued: "text-gray-500",
  retrieving: "text-blue-400",
  matching: "text-purple-400",
  analyzing: "text-amber-400",
  scoring: "text-red-400",
  complete: "text-green-400",
  error: "text-red-500",
};

const PHASE_BORDERS: Record<Phase, string> = {
  queued: "border-l-gray-700",
  retrieving: "border-l-blue-500",
  matching: "border-l-purple-500",
  analyzing: "border-l-amber-500",
  scoring: "border-l-red-500",
  complete: "border-l-green-500",
  error: "border-l-red-600",
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

interface PipelineRowProps {
  personId: string;
  name: string;
  phase: Phase;
  articleCount: number | null;
  scoreRange?: string;
  progress?: number;
}

export function PipelineRow({
  personId,
  name,
  phase,
  articleCount,
  scoreRange,
  progress,
}: PipelineRowProps) {
  const isActive = !["queued", "complete", "error"].includes(phase);

  return (
    <div
      className={`grid grid-cols-[200px_120px_100px_200px_80px] gap-2 items-center px-4 py-2.5 rounded-md border-l-[3px] ${
        PHASE_BORDERS[phase]
      } ${phase === "queued" ? "opacity-45" : ""}`}
    >
      <Link
        href={phase === "complete" ? `/results/${personId}` : "#"}
        className={`text-sm ${
          phase === "complete"
            ? "text-green-300 underline decoration-green-800"
            : "text-gray-200"
        }`}
      >
        {name}
      </Link>
      <span className="text-xs text-gray-600 font-mono">{personId}</span>
      <span className="text-sm text-gray-500">
        {articleCount ?? "\u2014"}
      </span>
      <div className="flex items-center gap-2">
        {isActive && (
          <span className={`text-xs animate-spin ${PHASE_COLORS[phase]}`}>
            {"\u25E0"}
          </span>
        )}
        {phase === "complete" && (
          <span className="text-green-500 text-sm">{"\u2713"}</span>
        )}
        <span className={`text-sm ${PHASE_COLORS[phase]}`}>
          {PHASE_LABELS[phase]}
        </span>
      </div>
      <div className="w-full">
        {isActive && progress !== undefined && (
          <Progress value={progress} className="h-1" />
        )}
        {phase === "complete" && scoreRange && (
          <span className="text-xs text-gray-600">{scoreRange}</span>
        )}
      </div>
    </div>
  );
}
