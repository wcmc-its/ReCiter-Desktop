// frontend/app/articles/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { apiUpload } from "@/lib/api";

export default function ArticlesPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{
    articles_fetched: number;
    links_created: number;
    total_pmids: number;
  } | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const res = await apiUpload<{
        articles_fetched: number;
        links_created: number;
        total_pmids: number;
      }>("/api/articles/upload", file);
      setResult(res);
    } finally {
      setUploading(false);
    }
  }

  if (result) {
    return (
      <div className="max-w-2xl">
        <h2 className="text-2xl font-semibold mb-6">Articles</h2>
        <Card className="border-green-800 bg-green-950/20">
          <CardContent className="p-6 text-center">
            <p className="text-green-400 text-lg font-medium mb-2">
              {result.total_pmids} PMIDs processed
            </p>
            <p className="text-green-500/70 text-sm">
              {result.articles_fetched} new articles fetched from PubMed &bull;{" "}
              {result.links_created} researcher-article links created
            </p>
            <Button className="mt-4" onClick={() => router.push("/pipeline")}>
              Continue to Pipeline
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-semibold mb-2">Articles</h2>
      <p className="text-gray-400 mb-6">
        Upload a list of known PMIDs to score. Use this when you already have
        publication lists and just need scores (Scoring Only mode).
      </p>
      <p className="text-gray-500 text-sm mb-6">
        If you want to discover new articles from PubMed instead, skip this page
        and run the pipeline in Full Retrieval and Scoring mode.
      </p>

      {uploading ? (
        <Card className="border-gray-800">
          <CardContent className="p-8 text-center">
            <p className="text-gray-400">
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
  );
}
