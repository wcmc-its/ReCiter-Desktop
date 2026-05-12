"use client";

import { createContext, useContext, useRef, useState, useEffect, ReactNode, useCallback } from "react";
import { Phase } from "@/components/pipeline-row";
import { apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";
import { useWorkflow } from "@/lib/workflow";

export interface ResearcherStatus {
  personId: string;
  name: string;
  phase: Phase;
  articleCount: number | null;
  scoreRange?: string;
}

interface LogEntry {
  time: string;
  msg: string;
  type: "info" | "success" | "error";
}

interface PipelineContextType {
  researchers: ResearcherStatus[];
  setResearchers: React.Dispatch<React.SetStateAction<ResearcherStatus[]>>;
  running: boolean;
  completed: number;
  total: number;
  totalArticles: number;
  totalScored: number;
  startTime: number | null;
  maxWorkers: number | null;
  currentRunId: number | null;
  avgTimePerResearcher: number;
  researcherStartTimes: Record<string, number>;
  processingSet: Set<string>;
  logLines: LogEntry[];
  pipelineFinished: boolean;
  summary: { high_confidence: number; review_band: number; unlikely: number } | null;
  orcidReport: OrcidReport | null;
  startPipeline: (mode: string) => void;
  cancelPipeline: () => void;
  resetPipeline: () => void;
}

interface OrcidReport {
  total_with_orcid: number;
  tier_counts: Record<string, number>;
  inferences: Array<{
    person_id: string;
    first_name: string;
    last_name: string;
    orcid: string;
    confidence_tier: string;
    confidence_score: number;
    accepted_articles: number;
    total_articles: number;
    identity_orcid: string;
    orcid_matches_identity: boolean;
  }>;
}

const PipelineContext = createContext<PipelineContextType | null>(null);

export function PipelineProvider({ children }: { children: ReactNode }) {
  const { refresh } = useWorkflow();

  const [researchers, setResearchers] = useState<ResearcherStatus[]>([]);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(0);
  const [total, setTotal] = useState(0);
  const [totalArticles, setTotalArticles] = useState(0);
  const [totalScored, setTotalScored] = useState(0);
  const [maxWorkers, setMaxWorkers] = useState<number | null>(null);
  const [currentRunId, setCurrentRunId] = useState<number | null>(null);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [avgTimePerResearcher, setAvgTimePerResearcher] = useState<number>(0);
  const [researcherStartTimes, setResearcherStartTimes] = useState<Record<string, number>>({});
  const [processingSet, setProcessingSet] = useState<Set<string>>(new Set());
  const [logLines, setLogLines] = useState<LogEntry[]>([]);
  const [pipelineFinished, setPipelineFinished] = useState(false);
  const [summary, setSummary] = useState<PipelineContextType["summary"]>(null);
  const [orcidReport, setOrcidReport] = useState<OrcidReport | null>(null);

  const personIdsRef = useRef<string[]>([]);
  const nextToStartRef = useRef<number>(0);
  const lastCompletionTimeRef = useRef<number | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  function addLog(msg: string, type: LogEntry["type"] = "info") {
    const t = new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setLogLines((prev) => [...prev.slice(-49), { time: t, msg, type }]);
  }

  const startPipeline = useCallback((mode: string) => {
    setRunning(true);
    setCompleted(0);
    setStartTime(Date.now());
    setAvgTimePerResearcher(0);
    setResearcherStartTimes({});
    setMaxWorkers(null);
    setCurrentRunId(null);
    setProcessingSet(new Set());
    setLogLines([]);
    setPipelineFinished(false);
    setSummary(null);
    setOrcidReport(null);
    lastCompletionTimeRef.current = null;

    const personIds = researchers.map((r) => r.personId);
    personIdsRef.current = personIds;
    nextToStartRef.current = 0;
    setTotal(personIds.length);
    setTotalArticles(0);
    setTotalScored(0);

    const nameMap = Object.fromEntries(researchers.map((r) => [r.personId, r.name]));

    const abort = subscribeSSE(
      "/api/pipeline/run",
      { person_ids: personIds, mode },
      (event) => {
        if (event.type === "started") {
          const mw = (event.max_workers as number) ?? 3;
          setMaxWorkers(mw);
          setCurrentRunId((event.run_id as number) ?? null);
          lastCompletionTimeRef.current = Date.now();
          const initialIds = personIdsRef.current.slice(0, mw);
          setProcessingSet(new Set(initialIds));
          nextToStartRef.current = Math.min(mw, personIdsRef.current.length);
          addLog(`Pipeline started — ${personIdsRef.current.length} researchers · ${mw} workers`);
        } else if (event.type === "queued") {
          const pid = event.person_id as string;
          setResearcherStartTimes((prev) => ({ ...prev, [pid]: Date.now() }));
          setResearchers((prev) =>
            prev.map((r) => (r.personId === pid ? { ...r, phase: "queued" } : r))
          );
        } else if (event.type === "complete_one") {
          const artCount = (event.article_count as number) || 0;
          const scoredCount = (event.scored_count as number) || 0;
          const scoreMin = event.score_min as number | undefined;
          const scoreMax = event.score_max as number | undefined;
          const completedCount = event.completed as number;
          const pid = event.person_id as string;

          setCompleted(completedCount);
          setTotalArticles((prev) => prev + artCount);
          setTotalScored((prev) => prev + scoredCount);

          const now = Date.now();
          if (lastCompletionTimeRef.current !== null) {
            const delta = now - lastCompletionTimeRef.current;
            setAvgTimePerResearcher((prev) => (prev === 0 ? delta : (prev + delta) / 2));
          }
          lastCompletionTimeRef.current = now;

          setProcessingSet((prev) => {
            const next = new Set(prev);
            next.delete(pid);
            const idx = nextToStartRef.current;
            if (idx < personIdsRef.current.length) {
              next.add(personIdsRef.current[idx]);
              nextToStartRef.current = idx + 1;
            }
            return next;
          });

          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === pid
                ? {
                    ...r,
                    phase: event.error ? "error" : ("complete" as Phase),
                    articleCount: artCount,
                    scoreRange:
                      scoreMin !== undefined && scoreMax !== undefined
                        ? `${Math.round(scoreMin * 100)}\u2013${Math.round(scoreMax * 100)}`
                        : undefined,
                  }
                : r
            )
          );

          const resName = nameMap[pid] ?? pid;
          if (event.error) {
            addLog(`\u2717 ${resName} — ${event.error as string}`, "error");
          } else {
            const scoreStr =
              scoreMin !== undefined && scoreMax !== undefined
                ? ` · scores ${Math.round(scoreMin * 100)}–${Math.round(scoreMax * 100)}`
                : "";
            addLog(`\u2713 ${resName} — ${scoredCount} articles${scoreStr}`, "success");
          }
        } else if (event.type === "finished") {
          setRunning(false);
          setPipelineFinished(true);
          setProcessingSet(new Set());
          addLog("Pipeline complete");
          refresh();
          apiFetch<{ high_confidence: number; review_band: number; unlikely: number }>(
            "/api/pipeline/status"
          )
            .then(setSummary)
            .catch(() => {});
          apiFetch<OrcidReport>("/api/scores/orcid-report")
            .then((d) => {
              if (d && d.total_with_orcid > 0) setOrcidReport(d);
            })
            .catch(() => {});
        }
      },
      () => {
        setRunning(false);
        setProcessingSet(new Set());
      }
    );
    abortRef.current = abort;
  }, [researchers, refresh]);

  const resetPipeline = useCallback(() => {
    setCompleted(0);
    setTotal(0);
    setTotalArticles(0);
    setTotalScored(0);
    setStartTime(null);
    setAvgTimePerResearcher(0);
    setResearcherStartTimes({});
    setProcessingSet(new Set());
    setLogLines([]);
    setPipelineFinished(false);
    setSummary(null);
    setOrcidReport(null);
    setMaxWorkers(null);
    setCurrentRunId(null);
    lastCompletionTimeRef.current = null;
    nextToStartRef.current = 0;
    personIdsRef.current = [];
  }, []);

  const cancelPipeline = useCallback(() => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    setRunning(false);
    setProcessingSet(new Set());
    addLog("Pipeline cancelled by user", "error");
    // Update backend run status if we have a run ID (best-effort, ignore failures)
    if (currentRunId) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090"}/api/pipeline/${currentRunId}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).catch(() => {});
    }
  }, [currentRunId]);

  // Load researchers on first mount
  useEffect(() => {
    async function loadResearchers() {
      try {
        const list = await apiFetch<
          Array<{
            person_id: string;
            first_name: string;
            last_name: string;
            article_count: number;
            score_count: number;
          }>
        >("/api/researchers");
        setResearchers(
          list.map((r) => ({
            personId: r.person_id,
            name: `${r.first_name} ${r.last_name}`,
            phase: (r.score_count > 0 ? "complete" : "queued") as Phase,
            articleCount: r.article_count || null,
          }))
        );
      } catch {
        // API not available
      }
    }
    loadResearchers();
  }, []);

  return (
    <PipelineContext.Provider
      value={{
        researchers,
        setResearchers,
        running,
        completed,
        total,
        totalArticles,
        totalScored,
        startTime,
        maxWorkers,
        currentRunId,
        avgTimePerResearcher,
        researcherStartTimes,
        processingSet,
        logLines,
        pipelineFinished,
        summary,
        orcidReport,
        startPipeline,
        cancelPipeline,
        resetPipeline,
      }}
    >
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline() {
  const ctx = useContext(PipelineContext);
  if (!ctx) throw new Error("usePipeline must be used within PipelineProvider");
  return ctx;
}
