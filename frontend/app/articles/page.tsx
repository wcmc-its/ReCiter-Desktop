// frontend/app/articles/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { apiUpload, apiFetch } from "@/lib/api";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { useWorkflow } from "@/lib/workflow";

interface ArticleSummary {
  person_id: string;
  first_name: string;
  last_name: string;
  article_count: number;
  uploaded: number;
  retrieved: number;
}

export default function ArticlesPage() {
  const { researcherCount, articleCount, uploadedArticles, refresh } = useWorkflow();
  const router = useRouter();
  const [replacing, setReplacing] = useState(false);
  const [summaries, setSummaries] = useState<ArticleSummary[] | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{
    articles_fetched: number;
    links_created: number;
    total_pmids: number;
  } | null>(null);

  useEffect(() => {
    if (articleCount > 0 && !replacing && !result) {
      apiFetch<ArticleSummary[]>("/api/articles").then(setSummaries);
    }
  }, [articleCount, replacing, result]);

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const res = await apiUpload<{
        articles_fetched: number;
        links_created: number;
        total_pmids: number;
      }>("/api/articles/upload", file);
      setResult(res);
      refresh();
    } finally {
      setUploading(false);
    }
  }

  // Success state
  if (result) {
    return (
      <div className="max-w-2xl">
        <h2 className="text-2xl font-semibold mb-6 text-gray-900">Articles</h2>
        <Card className="border-green-300 bg-green-50 shadow-sm">
          <CardContent className="p-6 text-center">
            <p className="text-green-700 text-lg font-medium mb-2">
              {result.total_pmids} PMIDs processed
            </p>
            <p className="text-green-600 text-sm">
              {result.articles_fetched} new articles fetched from PubMed &bull;{" "}
              {result.links_created} researcher-article links created
            </p>
            <Button
              className="mt-4 bg-[#cf4520] hover:bg-[#a3381a] text-white"
              onClick={() => router.push("/pipeline")}
            >
              Continue to Retrieve & Score
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Existing articles view
  if (articleCount > 0 && !replacing) {
    const totalUploaded = summaries?.reduce((s, r) => s + r.uploaded, 0) ?? uploadedArticles;

    return (
      <div className="max-w-3xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900">Known Articles</h2>
            <p className="text-gray-500 mt-1">
              {totalUploaded.toLocaleString()} articles uploaded as ground truth across {summaries?.length ?? "..."} researchers
            </p>
          </div>
          <Button variant="outline" onClick={() => setReplacing(true)}>
            Upload more
          </Button>
        </div>

        {/* Per-researcher table */}
        {summaries === null ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
            <div className="grid grid-cols-[2fr_1.5fr_1fr] bg-gray-50 px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
              <span>Researcher</span>
              <span>ID</span>
              <span className="text-right">Articles</span>
            </div>
            {summaries
              .sort((a, b) => b.uploaded - a.uploaded)
              .map((s) => (
                <Link
                  key={s.person_id}
                  href={`/results/${s.person_id}`}
                  className="grid grid-cols-[2fr_1.5fr_1fr] px-4 py-2.5 border-t border-gray-100 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <span className="font-medium truncate">
                    {s.last_name}, {s.first_name}
                  </span>
                  <span className="text-gray-400 font-mono text-xs">{s.person_id}</span>
                  <span className="text-right tabular-nums font-medium">{s.uploaded}</span>
                </Link>
              ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <PrerequisiteGate
      met={researcherCount > 0}
      message="Upload your researchers first so the system knows who to link articles to."
      actionLabel="Go to Researchers"
      actionHref="/researchers"
    >
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-2xl font-semibold text-gray-900">Articles</h2>
        {replacing && (
          <Button variant="ghost" size="sm" onClick={() => { setReplacing(false); }}>
            ← Back to list
          </Button>
        )}
      </div>
      <p className="text-gray-500 mb-6">
        {replacing
          ? "Upload additional PMIDs to add to the existing article set."
          : "Already have a list of publications? Upload PMIDs to score them directly. Use this when you already have publication lists and just need scores (Scoring Only mode)."}
      </p>
      {!replacing && (
        <p className="text-gray-400 text-sm mb-6">
          If you want to discover new articles from PubMed instead, skip this page
          and use Full Retrieval and Scoring mode on the next page.
        </p>
      )}

      {uploading ? (
        <Card className="border-gray-200 shadow-sm">
          <CardContent className="p-8 text-center">
            <p className="text-gray-500">
              Uploading PMIDs and fetching metadata from PubMed...
            </p>
          </CardContent>
        </Card>
      ) : (
        <FileUpload
          onFileSelected={handleFile}
          description="A spreadsheet with person_id and pmid columns. Each row links a researcher to an article."
        />
      )}
    </div>
    </PrerequisiteGate>
  );
}
