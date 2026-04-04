// frontend/app/results/[personId]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { ScoreBadge } from "@/components/score-badge";
import { apiFetch, apiExportUrl } from "@/lib/api";

interface ScoredArticle {
  pmid: string;
  score: number;
  title: string;
  journal: string;
  pub_year: number;
  doi: string;
  features: Record<string, number>;
}

interface ResearcherInfo {
  person_id: string;
  first_name: string;
  last_name: string;
}

const FEATURE_LABELS: Record<string, string> = {
  nameMatchFirstScore: "First name match",
  nameMatchLastScore: "Last name match",
  nameMatchMiddleScore: "Middle name match",
  nameMatchModifierScore: "Name modifier",
  emailMatchScore: "Email match",
  pubmedTargetAuthorInstitutionalAffiliationMatchScore: "Institutional affiliation",
  targetAuthorInstitutionalAffiliationScore: "Target author affiliation",
  organizationalUnitMatchingScore: "Department match",
  journalSubfieldScore: "Journal relevance",
  discrepancyDegreeYearScore: "Degree year",
  genderScoreIdentityArticleDiscrepancy: "Gender match",
  articleCountScore: "Article count",
  authorCountScore: "Author count",
};

export default function ResearcherResultsPage() {
  const params = useParams();
  const personId = params.personId as string;

  const [researcher, setResearcher] = useState<ResearcherInfo | null>(null);
  const [articles, setArticles] = useState<ScoredArticle[]>([]);
  const [threshold, setThreshold] = useState(70);
  const [sortBy, setSortBy] = useState<"score" | "year" | "journal">("score");
  const [expandedPmid, setExpandedPmid] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<ResearcherInfo>(`/api/researchers/${personId}`)
      .then(setResearcher)
      .catch(() => {});
    apiFetch<ScoredArticle[]>(`/api/scores/${personId}`)
      .then(setArticles)
      .catch(() => {});
  }, [personId]);

  const sorted = [...articles].sort((a, b) => {
    if (sortBy === "score") return b.score - a.score;
    if (sortBy === "year") return (b.pub_year || 0) - (a.pub_year || 0);
    return (a.journal || "").localeCompare(b.journal || "");
  });

  const above = articles.filter((a) => a.score >= threshold).length;
  const below = articles.length - above;

  if (!researcher) return <div className="text-gray-400">Loading...</div>;

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">
            {researcher.first_name} {researcher.last_name}
          </h2>
          <p className="text-gray-400 text-sm font-mono">{personId}</p>
          <p className="text-gray-500 text-sm mt-1">
            {articles.length} articles scored
          </p>
        </div>
        <a
          href={apiExportUrl("/api/scores/export", {
            person_id: personId,
            threshold: String(threshold),
          })}
          download
        >
          <Button variant="outline">Export CSV</Button>
        </a>
      </div>

      {/* Score distribution histogram */}
      {articles.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-gray-500 mb-2">Score distribution</p>
          <div className="flex items-end gap-0.5 h-16">
            {Array.from({ length: 10 }, (_, i) => {
              const lo = i * 10;
              const hi = i === 9 ? 101 : (i + 1) * 10;
              const count = articles.filter((a) => a.score >= lo && a.score < hi).length;
              const maxCount = Math.max(...Array.from({ length: 10 }, (_, j) => {
                const jlo = j * 10;
                const jhi = j === 9 ? 101 : (j + 1) * 10;
                return articles.filter((a) => a.score >= jlo && a.score < jhi).length;
              }));
              const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
              const inThreshold = lo >= threshold;
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                  <div
                    className={`w-full rounded-t ${inThreshold ? 'bg-green-400' : lo >= 30 ? 'bg-amber-300' : 'bg-red-300'}`}
                    style={{ height: `${pct}%`, minHeight: count > 0 ? '2px' : '0px' }}
                  />
                  <span className="text-[8px] text-gray-400">{lo}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Threshold slider */}
      <div className="flex items-center gap-4 mb-6">
        <span className="text-sm text-gray-500">Threshold:</span>
        <div className="w-48">
          <Slider
            value={threshold}
            onValueChange={(v) => setThreshold(v as number)}
            min={0}
            max={100}
            step={5}
          />
        </div>
        <span className="text-sm text-gray-700 font-mono w-8">{threshold}</span>
        <span className="text-sm text-green-600">{above} above</span>
        <span className="text-gray-300">|</span>
        <span className="text-sm text-red-500">{below} below</span>
      </div>

      {/* Sort */}
      <div className="flex gap-2 mb-4">
        {(["score", "year", "journal"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSortBy(s)}
            className={`text-xs px-3 py-1 rounded border ${
              sortBy === s
                ? "bg-gray-100 text-gray-900 border-gray-300"
                : "text-gray-500 border-transparent hover:bg-gray-50 hover:border-gray-200"
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Article table */}
      <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <div className="grid grid-cols-[60px_1fr_180px_60px_60px] gap-2 px-4 py-2 bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
          <span>Score</span>
          <span>Title</span>
          <span>Journal</span>
          <span>Year</span>
          <span />
        </div>
        {sorted.map((a) => {
          const isExpanded = expandedPmid === a.pmid;
          const topFeatures = Object.entries(a.features || {})
            .filter(([, v]) => v !== 0)
            .sort((x, y) => Math.abs(y[1]) - Math.abs(x[1]))
            .slice(0, 5);

          return (
            <div key={a.pmid} className="border-t border-gray-200">
              <div
                className="grid grid-cols-[60px_1fr_180px_60px_60px] gap-2 items-center px-4 py-2.5 bg-white cursor-pointer hover:bg-gray-50"
                onClick={() => setExpandedPmid(isExpanded ? null : a.pmid)}
              >
                <ScoreBadge score={a.score} />
                <span
                  className={`text-sm ${
                    a.score >= threshold ? "text-gray-900" : "text-gray-400"
                  }`}
                >
                  {a.title}
                </span>
                <span className="text-xs text-gray-500 truncate">{a.journal}</span>
                <span className="text-xs text-gray-500">{a.pub_year}</span>
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#cf4520]"
                  onClick={(e) => e.stopPropagation()}
                >
                  PubMed
                </a>
              </div>
              {isExpanded && topFeatures.length > 0 && (
                <div className="bg-gray-50 border-t border-gray-100 px-4 py-3 space-y-1.5">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-2">Top evidence</p>
                  {topFeatures.map(([key, val]) => (
                    <div key={key} className="flex items-center gap-3">
                      <span className="text-xs text-gray-600 w-48 shrink-0">
                        {FEATURE_LABELS[key] ?? key}
                      </span>
                      <div className="flex-1 bg-gray-200 rounded h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded ${val >= 0 ? 'bg-green-500' : 'bg-red-400'}`}
                          style={{ width: `${Math.min(Math.abs(val) * 100, 100)}%` }}
                        />
                      </div>
                      <span className={`text-xs font-mono w-12 text-right ${val >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                        {val.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
