"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusCard } from "@/components/status-card";
import { apiFetch } from "@/lib/api";

interface DashboardState {
  institution: string | null;
  researcherCount: number;
  articleCount: number;
  scoreCount: number;
  scoredResearchers: number;
}

export default function Dashboard() {
  const [state, setState] = useState<DashboardState>({
    institution: null,
    researcherCount: 0,
    articleCount: 0,
    scoreCount: 0,
    scoredResearchers: 0,
  });

  useEffect(() => {
    async function load() {
      try {
        const config = await apiFetch<Record<string, unknown>>("/api/institution");
        const status = await apiFetch<{
          total_researchers: number;
          total_articles: number;
          total_scores: number;
          scored_researchers: number;
        }>("/api/pipeline/status");

        setState({
          institution: (config.institution_label as string) || null,
          researcherCount: status.total_researchers,
          articleCount: status.total_articles,
          scoreCount: status.total_scores,
          scoredResearchers: status.scored_researchers,
        });
      } catch {
        // API not available yet
      }
    }
    load();
  }, []);

  const hasInstitution = !!state.institution;
  const hasResearchers = state.researcherCount > 0;
  const hasArticles = state.articleCount > 0;
  const hasScores = state.scoreCount > 0;

  // Determine next step
  let nextHref = "/setup";
  let nextLabel = "Set Up Your Institution";
  if (hasInstitution && !hasResearchers) {
    nextHref = "/researchers";
    nextLabel = "Upload Researchers";
  } else if (hasResearchers && !hasScores) {
    nextHref = "/pipeline";
    nextLabel = "Run Pipeline";
  } else if (hasScores) {
    nextHref = "/results";
    nextLabel = "View Results";
  }

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-semibold mb-2">ReCiter Desktop</h2>
      <p className="text-gray-400 mb-8">
        Score publications against researcher identities using machine learning.
        Upload a researcher list, retrieve articles from PubMed, and get
        confidence scores for each article-researcher match.
      </p>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatusCard
          stepNumber={1}
          label="Institution"
          value={state.institution || "Not configured"}
          isComplete={hasInstitution}
          isNext={!hasInstitution}
        />
        <StatusCard
          stepNumber={2}
          label="Researchers"
          value={hasResearchers ? `${state.researcherCount} loaded` : "Not uploaded"}
          isComplete={hasResearchers}
          isNext={hasInstitution && !hasResearchers}
        />
        <StatusCard
          stepNumber={3}
          label="Articles"
          value={hasArticles ? `${state.articleCount} retrieved` : "Not yet retrieved"}
          isComplete={hasArticles}
          isNext={hasResearchers && !hasArticles && !hasScores}
        />
        <StatusCard
          stepNumber={4}
          label="Scores"
          value={
            hasScores
              ? `${state.scoreCount} scored`
              : "Not yet scored"
          }
          isComplete={hasScores}
          isNext={hasArticles && !hasScores}
        />
      </div>

      <Link href={nextHref}>
        <Button size="lg">{nextLabel}</Button>
      </Link>

      {hasInstitution && (
        <Card className="mt-8 border-gray-800 bg-gray-900/50">
          <CardContent className="p-4">
            <p className="text-sm font-medium text-gray-300 mb-2">
              About Scoring Models
            </p>
            <p className="text-xs text-gray-500 leading-relaxed">
              Your scores are currently based on identity evidence alone (25
              features including name matching, email, affiliation, and more).
              Institutions that curate articles — accepting or rejecting
              individual matches — unlock a more powerful model with 43 features
              that learns from those decisions. Curation support is coming in a
              future release via Publication Manager.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
