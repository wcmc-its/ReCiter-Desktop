// frontend/app/pipeline/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { PipelineRow, Phase } from "@/components/pipeline-row";
import { apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";

interface ResearcherStatus {
  personId: string;
  name: string;
  phase: Phase;
  articleCount: number | null;
  scoreRange?: string;
}

export default function PipelinePage() {
  const [researchers, setResearchers] = useState<ResearcherStatus[]>([]);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(0);
  const [total, setTotal] = useState(0);
  const [totalArticles, setTotalArticles] = useState(0);
  const [totalScored, setTotalScored] = useState(0);
  const [mode, setMode] = useState<"full" | "score_only">("full");
  const hasExistingScores = researchers.some((r) => r.phase === "complete");
  const [showCompleted, setShowCompleted] = useState(false);

  useEffect(() => {
    async function loadResearchers() {
      try {
        const list = await apiFetch<Array<{
          person_id: string;
          first_name: string;
          last_name: string;
          article_count: number;
          score_count: number;
        }>>("/api/researchers");
        setResearchers(
          list.map((r) => ({
            personId: r.person_id,
            name: `${r.first_name} ${r.last_name}`,
            phase: r.score_count > 0 ? "complete" as Phase : "queued" as Phase,
            articleCount: r.article_count || null,
          }))
        );
      } catch {
        // API not available
      }
    }
    loadResearchers();
  }, []);

  function startPipeline() {
    setRunning(true);
    setCompleted(0);
    const personIds = researchers.map((r) => r.personId);
    setTotal(personIds.length);

    subscribeSSE(
      "/api/pipeline/run",
      { person_ids: personIds, mode },
      (event) => {
        if (event.type === "queued") {
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === event.person_id ? { ...r, phase: "queued" } : r
            )
          );
        } else if (event.type === "processing") {
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === event.person_id
                ? { ...r, phase: "retrieving" }
                : r
            )
          );
        } else if (event.type === "complete_one") {
          const artCount = event.article_count as number;
          const scoredCount = event.scored_count as number;
          const scoreMin = event.score_min as number | undefined;
          const scoreMax = event.score_max as number | undefined;
          setCompleted(event.completed as number);
          setTotalArticles((prev) => prev + artCount);
          setTotalScored((prev) => prev + scoredCount);
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === event.person_id
                ? {
                    ...r,
                    phase: event.error ? "error" : "complete",
                    articleCount: artCount,
                    scoreRange:
                      scoreMin !== undefined && scoreMax !== undefined
                        ? `${Math.round(scoreMin * 100)}\u2013${Math.round(scoreMax * 100)}`
                        : undefined,
                  }
                : r
            )
          );
        } else if (event.type === "finished") {
          setRunning(false);
        }
      },
      () => setRunning(false)
    );
  }

  const completedResearchers = researchers.filter((r) => r.phase === "complete");
  const activeResearchers = researchers.filter(
    (r) => !["complete", "queued"].includes(r.phase)
  );
  const queuedResearchers = researchers.filter((r) => r.phase === "queued");

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">Processing Pipeline</h2>
      <p className="text-gray-500 mb-6">
        Run the scoring pipeline for all researchers.
      </p>

      {!running && completed === 0 && (
        <div className="space-y-4 mb-6">
          <div className="flex gap-2">
            <Button
              variant={mode === "full" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("full")}
              className={mode === "full" ? "bg-[#cf4520] hover:bg-[#a3381a] text-white" : ""}
            >
              {hasExistingScores ? "Update (new publications only)" : "Full Retrieval and Scoring"}
            </Button>
            <Button
              variant={mode === "score_only" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("score_only")}
              className={mode === "score_only" ? "bg-[#cf4520] hover:bg-[#a3381a] text-white" : ""}
            >
              Scoring Only
            </Button>
          </div>
          {hasExistingScores && mode === "full" && (
            <p className="text-xs text-gray-400">
              Only newly added publications since the last run will be retrieved and scored.
              Previously scored articles are kept.
            </p>
          )}
          <Button
            onClick={startPipeline}
            disabled={researchers.length === 0}
            className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
          >
            Run Pipeline ({researchers.length} researchers)
          </Button>
        </div>
      )}

      {(running || completed > 0) && (
        <div className="mb-6">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Overall Progress</span>
            <span>
              {completed} of {total} researchers &bull; {totalArticles} articles
              &bull; {totalScored} scored
            </span>
          </div>
          <Progress value={total > 0 ? (completed / total) * 100 : 0} className="h-2" />
        </div>
      )}

      {/* Phase legend */}
      {(running || completed > 0) && (
        <div className="flex gap-4 mb-4 text-xs text-gray-500">
          <span><span className="text-green-600">{"\u25CF"}</span> Complete</span>
          <span><span className="text-blue-600">{"\u25CF"}</span> Retrieving</span>
          <span><span className="text-purple-600">{"\u25CF"}</span> Matching</span>
          <span><span className="text-amber-600">{"\u25CF"}</span> Analyzing</span>
          <span><span className="text-red-600">{"\u25CF"}</span> Scoring</span>
          <span><span className="text-gray-400">{"\u25CF"}</span> Queued</span>
        </div>
      )}

      {/* Researcher table — single flat list */}
      {(running || completed > 0 || researchers.length > 0) && (
        <div className="space-y-1">
          {/* Column headers */}
          <div className="grid grid-cols-[200px_120px_100px_200px_80px] gap-2 px-4 py-2 text-[10px] text-gray-500 uppercase tracking-wider border-b border-gray-200">
            <span>Researcher</span>
            <span>UID</span>
            <span>Articles</span>
            <span>Status</span>
            <span>Progress</span>
          </div>

          {/* Active researchers first */}
          {activeResearchers.map((r) => (
            <PipelineRow key={r.personId} {...r} />
          ))}

          {/* Queued researchers */}
          {queuedResearchers.length > 0 && running && (
            <>
              {queuedResearchers.slice(0, 5).map((r) => (
                <PipelineRow key={r.personId} {...r} />
              ))}
              {queuedResearchers.length > 5 && (
                <p className="text-center text-sm text-gray-400 py-2">
                  ... and {queuedResearchers.length - 5} more queued
                </p>
              )}
            </>
          )}

          {/* Completed researchers — collapsed */}
          {completedResearchers.length > 0 && (
            <div className="border-t border-gray-200 mt-2 pt-2">
              <button
                className="w-full flex items-center justify-between px-4 py-2 text-sm hover:bg-gray-50 rounded"
                onClick={() => setShowCompleted(!showCompleted)}
              >
                <span className="text-gray-600">
                  {"\u2713"} {completedResearchers.length} complete
                </span>
                <span className="text-gray-400 text-xs">
                  {showCompleted ? "Hide" : "Show"} {showCompleted ? "\u25B4" : "\u25BE"}
                </span>
              </button>
              {showCompleted &&
                completedResearchers.map((r) => (
                  <PipelineRow key={r.personId} {...r} />
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
