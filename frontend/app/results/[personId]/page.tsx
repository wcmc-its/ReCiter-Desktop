// frontend/app/results/[personId]/page.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ScoreBadge } from "@/components/score-badge";
import { apiFetch, apiDownload } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";

interface ScoredArticle {
  pmid: string;
  score: number;
  model_type: string;
  title: string;
  journal: string;
  pub_year: number;
  doi: string;
  features: { shap?: Record<string, number> };
  assertion: string | null;
}

interface ResearcherInfo {
  person_id: string;
  first_name: string;
  last_name: string;
}

const FEATURE_LABELS: Record<string, string> = {
  // Identity features
  nameMatchFirstScore: "First name match",
  nameMatchLastScore: "Last name match",
  nameMatchMiddleScore: "Middle name match",
  nameMatchModifierScore: "Name modifier",
  nameMatchMiddleAgreement: "Middle name agreement",
  nameMatchTypeOrdinal: "Name match type",
  emailMatchScore: "Email match",
  pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore: "Institutional affiliation",
  targetAuthorInstitutionalAffiliationMatchTypeScore: "Target author affiliation",
  scopusNonTargetAuthorInstitutionalAffiliationScore: "Non-target affiliation",
  organizationalUnitMatchingScore: "Department match",
  journalSubfieldScore: "Journal relevance",
  discrepancyDegreeYearScore: "Degree year",
  genderScoreIdentityArticleDiscrepancy: "Gender match",
  articleCountScore: "Article count",
  authorCountScore: "Author count",
  relationshipPositiveMatchScore: "Co-author match",
  relationshipNegativeMatchScore: "Co-author mismatch",
  relationshipIdentityCount: "Known co-authors",
  // Derived features
  firstNameFrequencyScore: "First name frequency",
  firstNameLength: "First name length",
  nameJaroWinkler: "Name similarity (Jaro-Winkler)",
  nameEditDistanceNorm: "Name edit distance",
  nameQualityMin: "Name quality (min)",
  nameAffilStrength: "Name + affiliation strength",
  identityStrength: "Identity strength",
  forenameLengthRatio: "Forename length ratio",
  firstMiddleCoverage: "First/middle coverage",
  firstMiddleMatchInteraction: "First × middle match",
  nameFrequencyMatchInteraction: "Name frequency × match",
  nameLengthMatchInteraction: "Name length × match",
  nameInstitutionInteraction: "Name × institution",
  nameConflictConfirmed: "Name conflict confirmed",
  ambiguityRisk: "Ambiguity risk",
  hasEmail: "Has email",
  hasGender: "Has gender data",
  hasOrgUnit: "Has org unit",
  hasTextEvidence: "Has text evidence",
  // Feedback features
  feedbackScoreBibliographicCoupling: "Bibliographic coupling",
  feedbackScoreCites: "Citation overlap",
  feedbackScoreCoAuthorName: "Co-author name (feedback)",
  feedbackScoreInstitution: "Institution (feedback)",
  feedbackScoreJournal: "Journal (feedback)",
  feedbackScoreJournalSubField: "Journal subfield (feedback)",
  feedbackScoreJournalTitleSimilarity: "Journal title similarity",
  feedbackScoreKeyword: "Keyword (feedback)",
  feedbackScoreOrcid: "ORCID (feedback)",
  feedbackScoreOrcidCoAuthor: "ORCID co-author (feedback)",
  feedbackScoreOrganization: "Organization (feedback)",
  feedbackScoreTargetAuthorName: "Target author name (feedback)",
  feedbackScoreTextSimilarity: "Text similarity (feedback)",
  feedbackConfidence: "Feedback confidence",
  feedbackDensity: "Feedback density",
  feedbackIdentityInteraction: "Feedback × identity",
  countAccepted: "Accepted count",
  countRejected: "Rejected count",
  acceptanceRateLowerBound: "Acceptance rate (lower bound)",
  // Interaction & risk features
  bibCouplingHighConfOnly: "Bib coupling (high conf)",
  bibCouplingFeedbackConfInteraction: "Bib coupling × confidence",
  hasBibCouplingSignal: "Has bib coupling signal",
  textSimAffilGapInteraction: "Text sim × affiliation gap",
  textSimFeedbackConfInteraction: "Text sim × feedback conf",
  textSimNewJournalInteraction: "Text sim × new journal",
  textSimNoCoauthorInteraction: "Text sim × no co-author",
  evidenceConsistency: "Evidence consistency",
  netEvidenceCount: "Net evidence count",
  netEvidenceCountExtended: "Net evidence (extended)",
  worstSingleEvidence: "Worst single evidence",
  worstSingleEvidenceExtended: "Worst evidence (extended)",
  informedAbsenceCount: "Informed absence count",
  informedAbsenceIntensity: "Informed absence intensity",
  uncertainRejectionRisk: "Uncertain rejection risk",
};

export default function ResearcherResultsPage() {
  const params = useParams();
  const personId = params.personId as string;

  const [researcher, setResearcher] = useState<ResearcherInfo | null>(null);
  const [articles, setArticles] = useState<ScoredArticle[]>([]);
  const [sortBy, setSortBy] = useState<"score" | "year" | "journal">("score");
  const [expandedPmid, setExpandedPmid] = useState<string | null>(null);
  const [rescoring, setRescoring] = useState(false);
  const rescoreAbortRef = useRef<(() => void) | null>(null);

  useEffect(() => () => rescoreAbortRef.current?.(), []);

  const fetchScores = useCallback(() => {
    apiFetch<ScoredArticle[]>(`/api/scores/${personId}`)
      .then(setArticles)
      .catch(() => {});
  }, [personId]);

  useEffect(() => {
    apiFetch<ResearcherInfo>(`/api/researchers/${personId}`)
      .then(setResearcher)
      .catch(() => {});
    fetchScores();
  }, [personId, fetchScores]);

  // Auto-expand article from hash (e.g., #pmid-12345678)
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.startsWith("#pmid-")) {
      const pmid = hash.slice(6);
      setExpandedPmid(pmid);
      setTimeout(() => {
        document.getElementById(`pmid-${pmid}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 300);
    }
  }, [articles]);

  function handleRescore() {
    setRescoring(true);
    rescoreAbortRef.current = subscribeSSE(
      "/api/pipeline/run",
      { person_ids: [personId], mode: "score_only" },
      () => {},
      () => {
        fetchScores();
        setRescoring(false);
        rescoreAbortRef.current = null;
      }
    );
  }

  const sorted = [...articles].sort((a, b) => {
    if (sortBy === "score") return b.score - a.score;
    if (sortBy === "year") return (b.pub_year || 0) - (a.pub_year || 0);
    return (a.journal || "").localeCompare(b.journal || "");
  });

  const accepted = articles.filter((a) => a.assertion === "ACCEPTED").length;
  const rejected = articles.filter((a) => a.assertion === "REJECTED").length;

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
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleRescore} disabled={rescoring}>
            {rescoring ? "Re-scoring…" : "Re-score"}
          </Button>
          <Button
            variant="outline"
            onClick={() => apiDownload("/api/scores/export", `scores-${personId}.csv`, { person_id: personId })}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {/* Score distribution histogram — colored by assertion */}
      {articles.length > 0 && (() => {
        const hasAssertions = articles.some((a) => a.assertion);
        const bins = Array.from({ length: 10 }, (_, i) => {
          const lo = i * 10;
          const hi = i === 9 ? 101 : (i + 1) * 10;
          const inBin = articles.filter((a) => a.score >= lo && a.score < hi);
          return {
            lo,
            accepted: inBin.filter((a) => a.assertion === "ACCEPTED").length,
            rejected: inBin.filter((a) => a.assertion === "REJECTED").length,
            uncurated: inBin.filter((a) => !a.assertion).length,
            total: inBin.length,
          };
        });
        const maxCount = Math.max(...bins.map((b) => b.total), 1);

        return (
          <div className="mb-6">
            <div className="flex justify-between text-xs text-gray-500 mb-2">
              <span>Score distribution {hasAssertions ? "by assertion" : ""}</span>
              {hasAssertions && <span>{accepted} accepted &middot; {rejected} rejected</span>}
            </div>
            <div className="flex items-end gap-1 overflow-hidden" style={{ height: "80px" }}>
              {bins.map((bin) => {
                const BAR_H = 80; // px, matches container
                const accPx = Math.round((bin.accepted / maxCount) * BAR_H);
                const rejPx = Math.round((bin.rejected / maxCount) * BAR_H);
                const uncPx = Math.round((bin.uncurated / maxCount) * BAR_H);
                const totalPx = accPx + rejPx + uncPx;
                return (
                  <div key={bin.lo} className="flex-1 flex flex-col items-center">
                    {hasAssertions ? (
                      <div
                        className="w-full rounded-t overflow-hidden cursor-default"
                        title={`Score ${bin.lo}–${bin.lo + 10}: ${bin.accepted} accepted, ${bin.rejected} rejected, ${bin.uncurated} no assertion`}
                      >
                        {bin.accepted > 0 && (
                          <div className="bg-green-400 w-full" style={{ height: `${accPx}px` }} />
                        )}
                        {bin.uncurated > 0 && (
                          <div className="bg-gray-300 w-full" style={{ height: `${uncPx}px` }} />
                        )}
                        {bin.rejected > 0 && (
                          <div className="bg-red-400 w-full" style={{ height: `${rejPx}px` }} />
                        )}
                      </div>
                    ) : (
                      <div
                        className={`w-full rounded-t ${bin.lo >= 70 ? "bg-green-400" : bin.lo >= 30 ? "bg-amber-300" : "bg-red-300"}`}
                        style={{ height: `${totalPx}px` }}
                      />
                    )}
                    <span className="text-[8px] text-gray-400 mt-0.5">{bin.lo}</span>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-center gap-4 text-xs mt-1.5">
              {hasAssertions ? (
                <>
                  <span className="flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-green-400" /> Accepted</span>
                  <span className="flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-400" /> Rejected</span>
                  <span className="flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-gray-300" /> No assertion</span>
                </>
              ) : (
                <>
                  <span className="text-red-400">Likely not a match</span>
                  <span className="text-gray-300">|</span>
                  <span className="text-green-600">Likely match</span>
                </>
              )}
            </div>
          </div>
        );
      })()}

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
        <div className="grid grid-cols-[60px_1fr_60px] sm:grid-cols-[60px_1fr_180px_60px_80px] gap-2 px-4 py-2 bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
          <span>Score</span>
          <span>Title</span>
          <span className="hidden sm:block">Journal</span>
          <span className="hidden sm:block">Year</span>
          <span className="hidden sm:block">Assertion</span>
        </div>
        {sorted.map((a) => {
          const isExpanded = expandedPmid === a.pmid;
          const shap = a.features?.shap ?? {};
          const shapEntries = Object.entries(shap)
            .filter(([, v]) => v !== 0)
            .sort((x, y) => Math.abs(y[1]) - Math.abs(x[1]))
            .slice(0, 12);
          const maxAbs = shapEntries.length > 0
            ? Math.max(...shapEntries.map(([, v]) => Math.abs(v)))
            : 1;
          const supports = shapEntries.filter(([, v]) => v > 0);
          const conflicts = shapEntries.filter(([, v]) => v < 0);

          return (
            <div key={a.pmid} id={`pmid-${a.pmid}`} className="border-t border-gray-200">
              <div
                className="grid grid-cols-[60px_1fr_60px] sm:grid-cols-[60px_1fr_180px_60px_80px] gap-2 items-center px-4 py-2.5 bg-white cursor-pointer hover:bg-gray-50"
                onClick={() => setExpandedPmid(isExpanded ? null : a.pmid)}
              >
                <ScoreBadge score={a.score} />
                <span className="text-sm text-gray-900">
                  {a.title}
                </span>
                <span className="hidden sm:block text-xs text-gray-500 truncate">{a.journal}</span>
                <span className="hidden sm:block text-xs text-gray-500">{a.pub_year}</span>
                <span className="hidden sm:block">
                  {a.assertion ? (
                    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${
                      a.assertion === "ACCEPTED"
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}>
                      {a.assertion.toLowerCase()}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-300">—</span>
                  )}
                </span>
              </div>
              {isExpanded && (
                <div className="bg-gray-50 border-t border-gray-100 px-4 py-4">
                  <div className="flex items-center gap-3 mb-3 text-xs">
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                    >
                      PubMed ↗
                    </a>
                    {a.doi && (
                      <a
                        href={`https://doi.org/${a.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                      >
                        DOI ↗
                      </a>
                    )}
                    <span className="text-gray-400 font-mono">PMID: {a.pmid}</span>
                    <span className="text-gray-400 ml-auto">
                      Model: {a.model_type === "feedbackIdentity" ? "Feedback + Identity" : "Identity only"}
                      {" "}({Object.keys(shap).length} features)
                    </span>
                  </div>
                  {supports.length > 0 && (
                    <div className="mb-3">
                      <p className="text-[9px] text-green-700 uppercase tracking-wider font-medium mb-2">Supports authorship</p>
                      {supports.map(([key, val]) => (
                        <div key={key} className="flex items-center gap-3 mb-1.5">
                          <span className="text-xs text-gray-600 w-52 shrink-0">{FEATURE_LABELS[key] || key.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase()).trim()}</span>
                          <div className="flex-1 bg-gray-200 rounded h-1.5 overflow-hidden">
                            <div className="h-full rounded bg-green-500" style={{ width: `${(Math.abs(val) / maxAbs) * 100}%` }} />
                          </div>
                          <span className="text-xs font-mono w-20 text-right text-green-600 whitespace-nowrap">+{val.toFixed(2)} pts</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {conflicts.length > 0 && (
                    <div>
                      <p className="text-[9px] text-red-500 uppercase tracking-wider font-medium mb-2">Against authorship</p>
                      {conflicts.map(([key, val]) => (
                        <div key={key} className="flex items-center gap-3 mb-1.5">
                          <span className="text-xs text-gray-600 w-52 shrink-0">{FEATURE_LABELS[key] || key.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase()).trim()}</span>
                          <div className="flex-1 bg-gray-200 rounded h-1.5 overflow-hidden">
                            <div className="h-full rounded bg-red-400" style={{ width: `${(Math.abs(val) / maxAbs) * 100}%` }} />
                          </div>
                          <span className="text-xs font-mono w-20 text-right text-red-500 whitespace-nowrap">{val.toFixed(2)} pts</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
