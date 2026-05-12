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
  lastRetrievalDate: string | null;
  pipelineRunning: boolean;
  loading: boolean;
  refresh: () => void;
  setPipelineRunning: (running: boolean) => void;
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
  lastRetrievalDate: null,
  pipelineRunning: false,
  loading: true,
  refresh: () => {},
  setPipelineRunning: () => {},
});

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<WorkflowState, "loading" | "refresh" | "setPipelineRunning">>({
    institution: null,
    researcherCount: 0,
    articleCount: 0,
    uploadedArticles: 0,
    searchedArticles: 0,
    scoreCount: 0,
    scoredResearchers: 0,
    assertionCount: 0,
    lastRetrievalDate: null,
    pipelineRunning: false,
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
          last_retrieval_date: string | null;
        }>("/api/pipeline/status"),
      ]);
      setState((prev) => ({
        ...prev,
        institution: (config.institution_label as string) || null,
        researcherCount: status.total_researchers,
        articleCount: status.total_articles,
        uploadedArticles: status.uploaded_articles,
        searchedArticles: status.searched_articles,
        scoreCount: status.total_scores,
        scoredResearchers: status.scored_researchers,
        assertionCount: status.assertion_count,
        lastRetrievalDate: status.last_retrieval_date,
      }));
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function setPipelineRunning(running: boolean) {
    setState((prev) => ({ ...prev, pipelineRunning: running }));
  }

  return (
    <WorkflowContext.Provider value={{ ...state, loading, refresh: load, setPipelineRunning }}>
      {children}
    </WorkflowContext.Provider>
  );
}

export function useWorkflow() {
  return useContext(WorkflowContext);
}
