"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useWorkflow } from "@/lib/workflow";

export default function Dashboard() {
  const {
    institution,
    researcherCount,
    articleCount,
    scoreCount,
    loading,
  } = useWorkflow();

  const hasInstitution = !!institution;
  const hasResearchers = researcherCount > 0;
  const hasScores = scoreCount > 0;

  // Determine next step
  let nextHref = "/setup";
  let nextLabel = "Get Started";
  let nextDescription = "Set up your institution to begin.";
  if (hasInstitution && !hasResearchers) {
    nextHref = "/researchers";
    nextLabel = "Upload Researchers";
    nextDescription = "Add your faculty roster to start finding their publications.";
  } else if (hasResearchers && !hasScores) {
    nextHref = "/pipeline";
    nextLabel = "Retrieve & Score";
    nextDescription = "Retrieve articles and compute authorship likelihood scores.";
  } else if (hasScores) {
    nextHref = "/results";
    nextLabel = "View Results";
    nextDescription = "Review scored articles and export your data.";
  }

  if (loading) {
    return (
      <div className="max-w-3xl">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">
        ReCiter Desktop
      </h2>
      <p className="text-gray-500 mb-8">
        Score publications against researcher identities using machine learning.
      </p>

      {/* Current status */}
      {(hasInstitution || hasResearchers || hasScores) && (
        <Card className="border-gray-200 shadow-sm mb-6">
          <CardContent className="p-5">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">
              Current Status
            </p>
            <div className="space-y-2">
              {hasInstitution && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-green-500">{"\u2713"}</span>
                  <span className="text-gray-700">
                    Institution: <strong>{institution}</strong>
                  </span>
                </div>
              )}
              {hasResearchers && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-green-500">{"\u2713"}</span>
                  <span className="text-gray-700">
                    {researcherCount.toLocaleString()} researchers loaded
                  </span>
                </div>
              )}
              {articleCount > 0 && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-green-500">{"\u2713"}</span>
                  <span className="text-gray-700">
                    {articleCount.toLocaleString()} articles retrieved
                  </span>
                </div>
              )}
              {hasScores && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-green-500">{"\u2713"}</span>
                  <span className="text-gray-700">
                    {scoreCount.toLocaleString()} articles scored
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Next step */}
      <Card className="border-[#cf4520]/30 bg-[#cf4520]/5 shadow-sm mb-8">
        <CardContent className="p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
            Next Step
          </p>
          <p className="text-sm text-gray-700 mb-3">{nextDescription}</p>
          <Link href={nextHref}>
            <Button className="bg-[#cf4520] hover:bg-[#a3381a] text-white">
              {nextLabel}
            </Button>
          </Link>
        </CardContent>
      </Card>

      {/* Education panel */}
      <Card className="border-gray-200 bg-white shadow-sm">
        <CardContent className="p-5">
          <p className="text-sm font-medium text-gray-800 mb-2">
            About CARE Scoring
          </p>
          <p className="text-xs text-gray-500 leading-relaxed">
            ReCiter Desktop uses the CARE (Composite Author Recognition Engine)
            scoring pipeline. Each article receives a calibrated confidence score
            from 0 to 100, representing the probability it belongs to the
            researcher.{" "}
            {hasScores ? (
              <>
                Your scores are based on identity evidence (47 features).
                Importing accept/reject curation data activates a more powerful
                72-feature model that reduces manual review from 18% to 2.3% of
                articles.
              </>
            ) : (
              <>
                The model was trained on over 900,000 curated articles at Weill
                Cornell Medicine and validated at external institutions with
                99.99% accuracy at the 99% confidence threshold.
              </>
            )}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
