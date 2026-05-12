"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch, apiDownload } from "@/lib/api";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { useWorkflow } from "@/lib/workflow";

interface OrcidInference {
  person_id: string;
  first_name: string;
  last_name: string;
  orcid: string;
  confidence_tier: string;
  confidence_score: number;
  accepted_articles: number;
  rejected_articles: number;
  total_articles: number;
  identity_orcid: string;
  orcid_matches_identity: boolean;
}

interface OrcidReport {
  total_with_orcid: number;
  tier_counts: Record<string, number>;
  inferences: OrcidInference[];
}

const TIERS = [
  { key: "confirmed", label: "Confirmed", color: "text-green-700", bg: "bg-green-100",
    description: "5+ high-confidence articles with the same ORCID, no contradictions" },
  { key: "likely", label: "Likely", color: "text-blue-700", bg: "bg-blue-100",
    description: "2-4 high-confidence articles with consistent ORCID" },
  { key: "possible", label: "Possible", color: "text-amber-700", bg: "bg-amber-100",
    description: "Single article with an ORCID at the target author position" },
  { key: "unreliable", label: "Unreliable", color: "text-red-600", bg: "bg-red-100",
    description: "Only in low-scoring articles, or competing ORCIDs found" },
];

const TIER_COLOR: Record<string, string> = {
  confirmed: "text-green-600",
  likely: "text-blue-600",
  possible: "text-amber-600",
  unreliable: "text-red-500",
};

export default function OrcidPage() {
  const { scoreCount } = useWorkflow();
  const [report, setReport] = useState<OrcidReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"feedback" | "scoring">("feedback");

  useEffect(() => {
    if (scoreCount > 0) {
      setLoading(true);
      apiFetch<OrcidReport>(`/api/scores/orcid-report?mode=${mode}`)
        .then(setReport)
        .catch(() => {})
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [scoreCount, mode]);

  return (
    <PrerequisiteGate
      met={scoreCount > 0}
      message="Retrieve and score articles first so there is ORCID data to analyze."
      actionLabel="Go to Results"
      actionHref="/results"
    >
      <div className="max-w-4xl">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-2xl font-semibold text-gray-900">ORCID Inference</h2>
          {report && report.total_with_orcid > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => apiDownload("/api/scores/orcid-report/export", "orcid-report.csv", { mode })}
            >
              Export CSV
            </Button>
          )}
        </div>
        <p className="text-gray-500 mb-4">
          ORCIDs inferred from the target author position in scored articles. Each researcher gets at most one ORCID
          — the one appearing most consistently across {mode === "feedback" ? "accepted" : "high-scoring"} articles.
        </p>

        <div className="flex items-center gap-2 mb-6">
          <span className="text-xs text-gray-500">Evidence basis:</span>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
            <button
              onClick={() => setMode("feedback")}
              className={`px-3 py-1.5 transition-colors ${
                mode === "feedback"
                  ? "bg-gray-900 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              Use Feedback
            </button>
            <button
              onClick={() => setMode("scoring")}
              className={`px-3 py-1.5 border-l border-gray-200 transition-colors ${
                mode === "scoring"
                  ? "bg-gray-900 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              Use Scoring
            </button>
          </div>
          <span className="text-[10px] text-gray-400">
            {mode === "feedback"
              ? "Tallies accepted vs. rejected decisions from curators"
              : "Educated guess based on scores above 95%"}
          </span>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="inline-block w-4 h-4 border-2 border-gray-200 border-t-gray-500 rounded-full animate-spin" />
            Analyzing ORCID evidence across scored articles…
          </div>
        ) : !report || report.total_with_orcid === 0 ? (
          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-6 text-center">
              <p className="text-gray-500 text-sm">
                No ORCIDs were found at the target author position in any scored articles.
                This is normal — not all PubMed records include ORCID identifiers.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* How it works */}
            <Card className="border-gray-200 bg-white shadow-sm">
              <CardContent className="p-5">
                <p className="text-sm font-medium text-gray-800 mb-2">How this works</p>
                <p className="text-xs text-gray-600 leading-relaxed">
                  For each researcher, the system examines the author identified as the target in each scored article.
                  If that author has an ORCID in the PubMed record, the ORCID is collected. When the same ORCID appears
                  consistently across multiple high-confidence articles, the system infers it belongs to the researcher.
                  Not all researchers will have an inferred ORCID — many PubMed records do not include ORCID data.
                </p>
              </CardContent>
            </Card>

            {/* Tier summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {TIERS.map((t) => (
                <div key={t.key} className={`rounded-lg p-4 ${t.bg}`}>
                  <p className={`text-2xl font-bold ${t.color}`}>
                    {report.tier_counts[t.key] || 0}
                  </p>
                  <p className={`text-xs font-medium ${t.color} mt-0.5`}>{t.label}</p>
                  <p className="text-[10px] text-gray-500 mt-1 leading-snug">{t.description}</p>
                </div>
              ))}
            </div>

            {/* Total */}
            <p className="text-xs text-gray-500">
              {report.total_with_orcid} of your researchers have at least one article with an ORCID at the target author position.
            </p>

            {/* Full table */}
            <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm text-xs">
              <div
                className="grid grid-cols-[1fr_160px_80px_70px] gap-2 px-4 py-2 bg-gray-50 text-gray-500 uppercase tracking-wider font-medium"
                style={{ fontSize: "10px" }}
              >
                <span>Researcher</span>
                <span>ORCID</span>
                <span>Tier</span>
                <span>Articles</span>
              </div>
              {report.inferences.map((r) => (
                <div
                  key={r.person_id}
                  className="grid grid-cols-[1fr_160px_80px_70px] gap-2 px-4 py-2 border-t border-gray-100 text-gray-700 hover:bg-gray-50"
                >
                  <span className="truncate">{r.first_name} {r.last_name}</span>
                  <a
                    href={`https://orcid.org/${r.orcid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#cf4520] truncate hover:underline"
                  >
                    {r.orcid}
                  </a>
                  <span className={TIER_COLOR[r.confidence_tier] || "text-gray-500"}>
                    {r.confidence_tier}
                  </span>
                  <span>
                    <span className="text-green-600">{r.accepted_articles}a</span>
                    {" / "}
                    <span className="text-red-500">{r.rejected_articles}r</span>
                    {r.total_articles - r.accepted_articles - r.rejected_articles > 0 && (
                      <>
                        {" / "}
                        <span className="text-gray-400">
                          {r.total_articles - r.accepted_articles - r.rejected_articles}n
                        </span>
                      </>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </PrerequisiteGate>
  );
}
