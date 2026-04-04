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
}

interface ResearcherInfo {
  person_id: string;
  first_name: string;
  last_name: string;
}

export default function ResearcherResultsPage() {
  const params = useParams();
  const personId = params.personId as string;

  const [researcher, setResearcher] = useState<ResearcherInfo | null>(null);
  const [articles, setArticles] = useState<ScoredArticle[]>([]);
  const [threshold, setThreshold] = useState(70);
  const [sortBy, setSortBy] = useState<"score" | "year" | "journal">("score");

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
        {sorted.map((a) => (
          <div
            key={a.pmid}
            className="grid grid-cols-[60px_1fr_180px_60px_60px] gap-2 items-center px-4 py-2.5 border-t border-gray-200 bg-white"
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
            >
              PubMed
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
