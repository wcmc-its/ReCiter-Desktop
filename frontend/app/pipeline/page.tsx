// frontend/app/pipeline/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PipelineRow, Phase } from "@/components/pipeline-row";
import { apiExportUrl } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { useWorkflow } from "@/lib/workflow";
import { usePipeline } from "@/lib/pipeline-context";

export default function PipelinePage() {
  const { researcherCount, assertionCount } = useWorkflow();
  const {
    researchers,
    running,
    completed,
    total,
    totalArticles,
    totalScored,
    startTime,
    maxWorkers,
    researcherStartTimes,
    processingSet,
    logLines,
    pipelineFinished,
    summary,
    startPipeline,
    cancelPipeline,
    resetPipeline,
  } = usePipeline();

  const [mode, setMode] = useState<"full" | "score_only">("full");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const hasExistingScores = researchers.some((r) => r.phase === "complete");

  // Tick every second while running so elapsed/remaining timers update
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  function formatDuration(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (minutes < 60) return `${minutes}m ${secs}s`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  }

  // Derive display phases: override "queued" → active phase for in-flight researchers
  const displayedResearchers = researchers.map((r) => {
    if (r.phase === "complete" || r.phase === "error") return r;
    if (processingSet.has(r.personId)) {
      return { ...r, phase: (mode === "score_only" ? "scoring" : "retrieving") as Phase };
    }
    return r;
  });

  const completedResearchers = displayedResearchers.filter((r) => r.phase === "complete");
  const activeResearchers = displayedResearchers.filter(
    (r) => !["complete", "queued", "error"].includes(r.phase)
  );
  const queuedResearchers = displayedResearchers.filter((r) => r.phase === "queued");

  // Determine bottleneck researchers: article-count-normalized rate, 5-minute floor
  const now = Date.now();
  const msPerArticle = startTime && totalArticles > 0
    ? (now - startTime) / totalArticles
    : 0;
  const bottleneckIds = new Set<string>(
    msPerArticle > 0
      ? activeResearchers
          .filter((r) => {
            const rStart = researcherStartTimes[r.personId];
            if (!rStart) return false;
            const expectedMs = (r.articleCount ?? 100) * msPerArticle;
            return (now - rStart) > Math.max(expectedMs * 2, 5 * 60 * 1000);
          })
          .map((r) => r.personId)
      : []
  );

  return (
    <PrerequisiteGate
      met={researcherCount > 0}
      message="Upload your researchers first so there is something to score."
      actionLabel="Go to Researchers"
      actionHref="/researchers"
    >
    <div className="max-w-4xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">Retrieve &amp; Score</h2>
      <p className="text-gray-500 mb-6">
        Retrieve articles and compute authorship likelihood scores for each researcher&apos;s candidate articles.
      </p>

      {!running && completed === 0 && (
        <div className="mb-6">
          {/* Tab bar */}
          <div className="flex border-b border-gray-200 mb-0">
            <button
              onClick={() => setMode("full")}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                mode === "full"
                  ? "border-[#cf4520] text-[#cf4520]"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {hasExistingScores ? "Update (new publications only)" : "Full Retrieval and Scoring"}
            </button>
            <button
              onClick={() => setMode("score_only")}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                mode === "score_only"
                  ? "border-[#cf4520] text-[#cf4520]"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Scoring Only
            </button>
          </div>

          {/* Tab content */}
          <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg p-5 shadow-sm">
            {mode === "full" ? (
              <div>
                <p className="text-sm text-gray-700 mb-1">
                  {hasExistingScores
                    ? "Search PubMed for newly added publications since the last run."
                    : "Search PubMed for each researcher by name to discover candidate publications."}
                </p>
                <p className="text-xs text-gray-400 mb-4">
                  {hasExistingScores
                    ? "Previously scored articles and their scores are preserved. Only new articles will be retrieved and scored."
                    : "The system retrieves articles, identifies the target author, computes evidence features, and scores each match."}
                </p>
              </div>
            ) : (
              <div>
                <p className="text-sm text-gray-700 mb-1">
                  Score articles you already uploaded via PMID CSV.
                </p>
                <p className="text-xs text-gray-400 mb-4">
                  Skips name-based PubMed discovery. Use this when article metadata is already in the database — a PMID list alone is not sufficient, since the full record (title, authors, affiliations, journal) must be retrieved before scoring.
                </p>
              </div>
            )}
            <Button
              onClick={() => startPipeline(mode)}
              disabled={researchers.length === 0}
              className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
            >
              Run Pipeline ({researchers.length} researchers)
            </Button>
          </div>
        </div>
      )}

      {(running || completed > 0) && (
        <div className="mb-6">
          <div className="flex justify-between items-center text-xs text-gray-500 mb-1">
            <span>Overall Progress</span>
            <div className="flex items-center gap-3">
              <span>
                {completed} of {total} researchers &bull; {totalArticles.toLocaleString()} articles
                &bull; {totalScored.toLocaleString()} scored
              </span>
              {running && (
                <button
                  onClick={() => setConfirmCancel(true)}
                  className="px-2 py-0.5 text-xs text-red-600 border border-red-200 rounded hover:bg-red-50 transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
          <div className="relative h-3.5 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className={`h-full rounded-full transition-[width] duration-500 ${running ? "pipeline-progress-animated" : "bg-blue-500"}`}
              style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
            />
          </div>
          {running && startTime && (
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>Elapsed: {formatDuration(Date.now() - startTime)}</span>
              <div className="flex gap-4">
                {maxWorkers && (
                  <span>Workers: <strong className="text-gray-600">{Math.min(total - completed, maxWorkers)}/{maxWorkers} active</strong></span>
                )}
                {completed > 0 && msPerArticle > 0 && maxWorkers && (
                  <span>Est. remaining: {formatDuration(
                    [...activeResearchers, ...queuedResearchers]
                      .reduce((sum, r) => sum + (r.articleCount ?? 100), 0) * msPerArticle / maxWorkers
                  )}</span>
                )}
              </div>
            </div>
          )}
          {logLines.length > 0 && (
            <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5 overflow-y-auto" style={{ maxHeight: "148px" }}>
              <p className="text-[9px] uppercase tracking-wider text-gray-400 font-semibold mb-1.5">Activity</p>
              <div className="space-y-0.5 font-mono text-xs">
                {[...logLines].reverse().map((entry, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="text-gray-400 shrink-0">{entry.time}</span>
                    <span className={entry.type === "success" ? "text-green-600" : entry.type === "error" ? "text-red-500" : "text-gray-500"}>
                      {entry.msg}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {(running || completed > 0) && (
        <div className="flex gap-4 mb-4 text-xs text-gray-500">
          <span><span className="text-blue-500">{"\u25CF"}</span> Processing</span>
          <span><span className="text-green-600">{"\u25CF"}</span> Complete</span>
          <span><span className="text-gray-400">{"\u25CF"}</span> Queued</span>
          <span><span className="text-red-500">{"\u25CF"}</span> Error</span>
        </div>
      )}

      {/* Researcher table — single flat list */}
      {(running || completed > 0 || researchers.length > 0) && (
        <div className="space-y-1">
          {/* Column headers — grid must match PipelineRow's grid-cols-[1.5fr_1fr_0.6fr_1.2fr_1fr] px-5 */}
          <div className="grid grid-cols-[1.5fr_1fr_0.6fr_1.2fr_1fr] gap-2 px-5 py-2 text-[10px] text-gray-500 uppercase tracking-wider border-b border-gray-200">
            <span>Researcher</span>
            <span>UID</span>
            <span>Articles</span>
            <span>Status</span>
            <span>Progress</span>
          </div>

          {/* Active researchers first */}
          {activeResearchers.map((r) => (
            <PipelineRow key={r.personId} {...r} isBottleneck={bottleneckIds.has(r.personId)} />
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

          {/* Completed researchers */}
          {completedResearchers.length > 0 && (
            <>
              {completedResearchers.map((r) => (
                <PipelineRow key={r.personId} {...r} />
              ))}
            </>
          )}
        </div>
      )}

      {/* ── Completion Summary ── */}
      {pipelineFinished && summary && (
        <div className="mt-8 space-y-6">
          <div className="border-t-2 border-green-400 pt-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">
              Pipeline Complete
            </h3>
            <p className="text-sm text-gray-500 mb-6">
              {totalScored.toLocaleString()} articles scored across{" "}
              {completed} researchers.
              {startTime && (
                <> Total time: {formatDuration(Date.now() - startTime)}.</>
              )}
            </p>
          </div>

          {/* Confidence tier cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="border-green-200 bg-green-50 shadow-sm">
              <CardContent className="p-5">
                <p className="text-3xl font-bold text-green-700">
                  {summary.high_confidence.toLocaleString()}
                </p>
                <p className="text-sm font-medium text-green-800 mt-1">
                  High Confidence
                </p>
                <p className="text-xs text-green-600 mt-2 leading-relaxed">
                  These articles scored 95 or above, meaning there is at least a
                  95% probability they belong to the researcher. In validation
                  testing, 99.95% of articles at this level were correctly
                  attributed.
                </p>
              </CardContent>
            </Card>

            <Card className="border-amber-200 bg-amber-50 shadow-sm">
              <CardContent className="p-5">
                <p className="text-3xl font-bold text-amber-700">
                  {summary.review_band.toLocaleString()}
                </p>
                <p className="text-sm font-medium text-amber-800 mt-1">
                  Needs Review
                </p>
                <p className="text-xs text-amber-700 mt-2 leading-relaxed">
                  These articles scored between 30 and 95. The system found some
                  matching evidence but not enough for high confidence. A
                  librarian or curator should review these to confirm or reject.
                </p>
              </CardContent>
            </Card>

            <Card className="border-red-200 bg-red-50 shadow-sm">
              <CardContent className="p-5">
                <p className="text-3xl font-bold text-red-600">
                  {summary.unlikely.toLocaleString()}
                </p>
                <p className="text-sm font-medium text-red-700 mt-1">
                  Unlikely Match
                </p>
                <p className="text-xs text-red-600 mt-2 leading-relaxed">
                  These articles scored below 30, meaning they are very unlikely
                  to belong to the researcher. They typically appear because the
                  researcher shares a common name with other authors.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* What these numbers mean */}
          <Card className="border-gray-200 bg-white shadow-sm">
            <CardContent className="p-5">
              <p className="text-sm font-medium text-gray-800 mb-3">
                What do these scores mean?
              </p>
              <div className="space-y-3 text-xs text-gray-600 leading-relaxed">
                <p>
                  Each score represents a <strong>calibrated probability</strong>{" "}
                  that the article belongs to the researcher. A score of 95 means
                  approximately 95 out of 100 articles at that confidence level are
                  correctly attributed. This is different from most disambiguation
                  systems, which produce rankings rather than true probabilities.
                </p>
                <p>
                  The model was trained on over 900,000 curated article-researcher
                  pairs at Weill Cornell Medicine and validated at external
                  institutions including Fred Hutchinson Cancer Center (868
                  researchers, 99.995% accuracy at the 99% threshold).
                </p>
                <p>
                  <strong>Tip:</strong> If you have accept/reject decisions from
                  prior curation work, import them on the Researchers page. This
                  activates a more powerful 72-feature model that reduces the
                  &quot;Needs Review&quot; count by up to 87%.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Next steps */}
          <div className="flex gap-3 flex-wrap">
            <Link href="/results">
              <Button className="bg-[#cf4520] hover:bg-[#a3381a] text-white">
                View Results
              </Button>
            </Link>
            {assertionCount > 0 && (
              <Link href="/stats">
                <Button className="bg-[#cf4520] hover:bg-[#a3381a] text-white">
                  View Statistics
                </Button>
              </Link>
            )}
            <a href={apiExportUrl("/api/scores/export")} download>
              <Button variant="outline">Export All Scores (CSV)</Button>
            </a>
            <Button variant="outline" onClick={resetPipeline}>
              Run again
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Cancel pipeline run?"
        description={
          <p className="text-xs text-gray-500">
            The run will be marked <span className="font-mono">PARTIAL</span>. You can resume
            scoring later from the Retrieve &amp; Score page.
          </p>
        }
        preserved={["Completed researchers and their scores remain in the database"]}
        destroyed={[
          "Researchers currently being scored will be stopped mid-run; in-flight work is lost",
          "Queued researchers will not be processed",
        ]}
        confirmLabel="Cancel run"
        cancelLabel="Keep running"
        onConfirm={cancelPipeline}
      />
    </div>
    </PrerequisiteGate>
  );
}
