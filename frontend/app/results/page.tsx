// frontend/app/results/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { apiFetch, apiExportUrl } from "@/lib/api";

interface Researcher {
  person_id: string;
  first_name: string;
  last_name: string;
  article_count: number;
  score_count: number;
}

export default function ResultsPage() {
  const [researchers, setResearchers] = useState<Researcher[]>([]);

  useEffect(() => {
    apiFetch<Researcher[]>("/api/researchers").then(setResearchers).catch(() => {});
  }, []);

  const scored = researchers.filter((r) => r.score_count > 0);

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">Results</h2>
          <p className="text-gray-500 text-sm">
            {scored.length} researchers scored
          </p>
        </div>
        {scored.length > 0 && (
          <a href={apiExportUrl("/api/scores/export")} download>
            <Button variant="outline">Export All Results (CSV)</Button>
          </a>
        )}
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <div className="grid grid-cols-[200px_120px_100px_100px_100px] gap-2 px-4 py-2 bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
          <span>Researcher</span>
          <span>UID</span>
          <span>Articles</span>
          <span>Scored</span>
          <span />
        </div>
        {scored.map((r) => (
          <Link
            key={r.person_id}
            href={`/results/${r.person_id}`}
            className="grid grid-cols-[200px_120px_100px_100px_100px] gap-2 items-center px-4 py-3 border-t border-gray-200 hover:bg-gray-50 transition-colors"
          >
            <span className="text-sm text-gray-900">
              {r.first_name} {r.last_name}
            </span>
            <span className="text-xs text-gray-400 font-mono">
              {r.person_id}
            </span>
            <span className="text-sm text-gray-500">{r.article_count}</span>
            <span className="text-sm text-gray-500">{r.score_count}</span>
            <span className="text-xs text-[#cf4520]">
              View articles {"\u2192"}
            </span>
          </Link>
        ))}
        {scored.length === 0 && (
          <div className="px-4 py-8 text-center text-gray-400">
            No results yet. Go to the Pipeline page to retrieve and score articles for your researchers.
          </div>
        )}
      </div>
    </div>
  );
}
