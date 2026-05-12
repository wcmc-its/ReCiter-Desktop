"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { apiFetch } from "@/lib/api";

interface WorkflowState {
  institution: string | null;
  researcherCount: number;
  articleCount: number;
  uploadedArticles: number;
  searchedArticles: number;
  scoreCount: number;
  scoredResearchers: number;
  assertionCount: number;
  loading: boolean;
  refresh: () => void;
}

const WorkflowContext = createContext<WorkflowState>({
  institution: null,
  researcherCount: 0,
  articleCount: 0,
  uploadedArticles: 0,
  searchedArticles: 0,
  scoreCount: 0,
  scoredResearchers: 0,
  assertionCount: 0,
  loading: true,
  refresh: () => {},
});

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<WorkflowState, "loading" | "refresh">>({
    institution: null,
    researcherCount: 0,
    articleCount: 0,
    uploadedArticles: 0,
    searchedArticles: 0,
    scoreCount: 0,
    scoredResearchers: 0,
    assertionCount: 0,
  });
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [config, status] = await Promise.all([
        apiFetch<Record<string, unknown>>("/api/institution"),
        apiFetch<{
          total_researchers: number;
          total_articles: number;
          uploaded_articles: number;
          searched_articles: number;
          total_scores: number;
          scored_researchers: number;
          assertion_count: number;
        }>("/api/pipeline/status"),
      ]);
      setState({
        institution: (config.institution_label as string) || null,
        researcherCount: status.total_researchers,
        articleCount: status.total_articles,
        uploadedArticles: status.uploaded_articles,
        searchedArticles: status.searched_articles,
        scoreCount: status.total_scores,
        scoredResearchers: status.scored_researchers,
        assertionCount: status.assertion_count,
      });
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <WorkflowContext.Provider value={{ ...state, loading, refresh: load }}>
      {children}
    </WorkflowContext.Provider>
  );
}

export function useWorkflow() {
  return useContext(WorkflowContext);
}
