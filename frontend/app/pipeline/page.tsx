// frontend/app/pipeline/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { PipelineRow, Phase } from "@/components/pipeline-row";
import { InfoTip } from "@/components/info-tip";
import { apiFetch, apiExportUrl } from "@/lib/api";
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

  // Timing state
  const [startTime, setStartTime] = useState<number | null>(null);
  const [avgTimePerResearcher, setAvgTimePerResearcher] = useState<number>(0);
  const [researcherStartTimes, setResearcherStartTimes] = useState<Record<string, number>>({});
  const [pipelineFinished, setPipelineFinished] = useState(false);
  const [summary, setSummary] = useState<{
    high_confidence: number;
    review_band: number;
    unlikely: number;
  } | null>(null);

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

  function startPipeline() {
    setRunning(true);
    setCompleted(0);
    setStartTime(Date.now());
    setAvgTimePerResearcher(0);
    setResearcherStartTimes({});
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
          const pid = event.person_id as string;
          setResearcherStartTimes((prev) => ({ ...prev, [pid]: Date.now() }));
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === pid
                ? { ...r, phase: "retrieving" }
                : r
            )
          );
        } else if (event.type === "complete_one") {
          const artCount = event.article_count as number;
          const scoredCount = event.scored_count as number;
          const scoreMin = event.score_min as number | undefined;
          const scoreMax = event.score_max as number | undefined;
          const completedCount = event.completed as number;

          setCompleted(completedCount);
          setTotalArticles((prev) => prev + artCount);
          setTotalScored((prev) => prev + scoredCount);

          // Update rolling average using startTime from closure
          setStartTime((prevStart) => {
            if (prevStart !== null) {
              const elapsed = Date.now() - prevStart;
              const avg = elapsed / completedCount;
              setAvgTimePerResearcher(avg);
            }
            return prevStart;
          });

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
          setPipelineFinished(true);
          apiFetch<{
            high_confidence: number;
            review_band: number;
            unlikely: number;
          }>("/api/pipeline/status").then(setSummary).catch(() => {});
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

  // Determine bottleneck researchers: processing time > 2x average
  const now = Date.now();
  const bottleneckIds = new Set<string>(
    avgTimePerResearcher > 0
      ? activeResearchers
          .filter((r) => {
            const rStart = researcherStartTimes[r.personId];
            return rStart !== undefined && (now - rStart) > avgTimePerResearcher * 2;
          })
          .map((r) => r.personId)
      : []
  );

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">Processing Pipeline</h2>
      <p className="text-gray-500 mb-6">
        Retrieve articles and compute confidence scores for each researcher.
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
            {!hasExistingScores && (
              <InfoTip text="Searches PubMed by researcher name to discover all candidate publications, then scores each one." />
            )}
            <Button
              variant={mode === "score_only" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("score_only")}
              className={mode === "score_only" ? "bg-[#cf4520] hover:bg-[#a3381a] text-white" : ""}
            >
              Scoring Only
            </Button>
            <InfoTip text="Scores only the articles you uploaded via PMID CSV. No PubMed search." />
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
          {running && completed > 0 && startTime && (
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>
                Elapsed: {formatDuration(Date.now() - startTime)}
              </span>
              <span>
                Est. remaining: {formatDuration(avgTimePerResearcher * (total - completed))}
              </span>
            </div>
          )}
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
                  These articles scored between 10 and 95. The system found some
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
                  These articles scored below 10, meaning they are very unlikely
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
          <div className="flex gap-3">
            <Link href="/results">
              <Button className="bg-[#cf4520] hover:bg-[#a3381a] text-white">
                View Results
              </Button>
            </Link>
            <a href={apiExportUrl("/api/scores/export")} download>
              <Button variant="outline">Export All Scores (CSV)</Button>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
