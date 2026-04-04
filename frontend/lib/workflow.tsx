"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { apiFetch } from "@/lib/api";

interface WorkflowState {
  institution: string | null;
  researcherCount: number;
  articleCount: number;
  scoreCount: number;
  scoredResearchers: number;
  loading: boolean;
  refresh: () => void;
}

const WorkflowContext = createContext<WorkflowState>({
  institution: null,
  researcherCount: 0,
  articleCount: 0,
  scoreCount: 0,
  scoredResearchers: 0,
  loading: true,
  refresh: () => {},
});

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<WorkflowState, "loading" | "refresh">>({
    institution: null,
    researcherCount: 0,
    articleCount: 0,
    scoreCount: 0,
    scoredResearchers: 0,
  });
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [config, status] = await Promise.all([
        apiFetch<Record<string, unknown>>("/api/institution"),
        apiFetch<{
          total_researchers: number;
          total_articles: number;
          total_scores: number;
          scored_researchers: number;
        }>("/api/pipeline/status"),
      ]);
      setState({
        institution: (config.institution_label as string) || null,
        researcherCount: status.total_researchers,
        articleCount: status.total_articles,
        scoreCount: status.total_scores,
        scoredResearchers: status.scored_researchers,
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
