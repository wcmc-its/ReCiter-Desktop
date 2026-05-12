// frontend/app/articles/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { ColumnMapper } from "@/components/column-mapper";
import { apiUpload, apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";
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

interface MappingRow {
  original: string;
  canonical: string | null;
  sample: string;
  selected: boolean;
}

interface UploadResult {
  file_id: string;
  filename: string;
  row_count: number;
  mappings: Array<{ original: string; canonical: string | null; sample: string }>;
  preview: Array<Record<string, unknown>>;
  has_gold_standard: boolean;
  gold_standard_count: number;
}

interface ImportResult {
  articles_fetched: number;
  links_created: number;
  curations_imported: number;
  total_pmids: number;
  already_existed: number;
}

export default function ArticlesPage() {
  const { researcherCount, articleCount, uploadedArticles, refresh } = useWorkflow();
  const router = useRouter();
  const [replacing, setReplacing] = useState(false);
  const [summaries, setSummaries] = useState<ArticleSummary[] | null>(null);

  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [importGoldStandard, setImportGoldStandard] = useState(true);

  const [parsing, setParsing] = useState(false);
  const [parsingFilename, setParsingFilename] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const [importing, setImporting] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [batchErrors, setBatchErrors] = useState<string[]>([]);
  const [progress, setProgress] = useState<{
    batch: number;
    batches: number;
    fetched: number;
    total: number;
  } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const importAbortRef = useRef<(() => void) | null>(null);

  useEffect(() => () => importAbortRef.current?.(), []);

  useEffect(() => {
    if (articleCount > 0 && !replacing && !importResult) {
      apiFetch<ArticleSummary[]>("/api/articles").then(setSummaries);
    }
  }, [articleCount, replacing, importResult]);

  useEffect(() => {
    if (importResult) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importResult]);

  async function handleFile(file: File) {
    setParsing(true);
    setParsingFilename(file.name);
    setParseError(null);
    try {
      const result = await apiUpload<UploadResult>("/api/articles/upload", file);
      setUploadResult(result);
      setMappings(
        result.mappings.map((m) => ({ ...m, selected: !!m.canonical }))
      );
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Failed to parse file");
    } finally {
      setParsing(false);
    }
  }

  function handleImport() {
    if (!uploadResult) return;
    setImporting(true);
    setStatusMessages([]);
    setBatchErrors([]);
    setProgress(null);
    setImportError(null);

    importAbortRef.current = subscribeSSE(
      "/api/articles/import",
      {
        file_id: uploadResult.file_id,
        mappings: mappings
          .filter((m) => m.selected && m.canonical)
          .map((m) => ({ original: m.original, canonical: m.canonical })),
        import_gold_standard: importGoldStandard,
      },
      (event) => {
        if (event.type === "status") {
          setStatusMessages((prev) => [...prev, event.message as string]);
        } else if (event.type === "fetch_progress") {
          setProgress({
            batch: event.batch as number,
            batches: event.batches as number,
            fetched: event.fetched as number,
            total: event.total as number,
          });
          if (event.error) {
            setBatchErrors((prev) => [
              ...prev,
              `Batch ${event.batch}: ${event.error as string}`,
            ]);
          }
        } else if (event.type === "error") {
          setImportError(event.message as string);
        } else if (event.type === "complete") {
          setImportResult({
            articles_fetched: event.articles_fetched as number,
            links_created: event.links_created as number,
            curations_imported: event.curations_imported as number,
            total_pmids: event.total_pmids as number,
            already_existed: event.already_existed as number,
          });
        }
      },
      () => {
        setImporting(false);
        importAbortRef.current = null;
      }
    );
  }

  // Success state
  if (importResult) {
    return (
      <div className="max-w-2xl">
        <h2 className="text-2xl font-semibold mb-6 text-gray-900">Articles</h2>
        <Card className="border-green-300 bg-green-50 shadow-sm">
          <CardContent className="p-6 text-center">
            <p className="text-green-700 text-lg font-medium mb-2">
              {importResult.total_pmids} PMIDs processed
            </p>
            <p className="text-green-600 text-sm">
              {importResult.articles_fetched} new articles fetched from PubMed &bull;{" "}
              {importResult.links_created} researcher-article links created
              {importResult.curations_imported > 0 && (
                <>
                  {" "}&bull; {importResult.curations_imported} curations imported
                </>
              )}
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

  const fetchPct = progress && progress.total > 0
    ? Math.min(100, Math.round((progress.fetched / progress.total) * 100))
    : 0;

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
          <Button
            variant="ghost"
            size="sm"
            disabled={importing}
            onClick={() => {
              setReplacing(false);
              setUploadResult(null);
              setMappings([]);
            }}
          >
            ← Back to list
          </Button>
        )}
      </div>
      <p className="text-gray-500 mb-6">
        {replacing
          ? "Upload additional PMIDs to add to the existing article set."
          : "Already have a list of publications? Upload PMIDs to score them directly. Use this when you already have publication lists and just need scores (Scoring Only mode)."}
      </p>
      {!replacing && !uploadResult && (
        <p className="text-gray-400 text-sm mb-6">
          If you want to discover new articles from PubMed instead, skip this page
          and use Full Retrieval and Scoring mode on the next page.
        </p>
      )}

      {!uploadResult ? (
        parsing ? (
          <Card className="border-gray-200 shadow-sm">
            <CardContent className="p-8 flex items-center gap-3 justify-center">
              <span className="inline-block w-4 h-4 border-2 border-[#cf4520] border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-gray-700">
                Parsing <span className="font-mono text-gray-900">{parsingFilename}</span>…
              </p>
            </CardContent>
          </Card>
        ) : parseError ? (
          <Card className="border-red-300 bg-red-50 shadow-sm">
            <CardContent className="p-5">
              <p className="text-sm font-medium text-red-700 mb-1">Couldn&apos;t parse {parsingFilename}</p>
              <p className="text-xs text-red-600 mb-3 break-words">{parseError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setParseError(null); setParsingFilename(null); }}
              >
                Try a different file
              </Button>
            </CardContent>
          </Card>
        ) : (
          <FileUpload
            onFileSelected={handleFile}
            description="A spreadsheet with person_id and pmid columns. Each row links a researcher to an article. Optional assertion column (ACCEPTED/REJECTED) imports as curation data."
            templateHref="/articles-template.csv"
          />
        )
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {uploadResult.filename} — {uploadResult.row_count} rows
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={importing}
              onClick={() => {
                setUploadResult(null);
                setMappings([]);
                setParsingFilename(null);
              }}
            >
              Upload different file
            </Button>
          </div>

          <ColumnMapper
            mappings={mappings}
            disabled={importing}
            availableFields={["person_id", "pmid", "assertion"]}
            onMappingChange={(i, canonical) => {
              const updated = [...mappings];
              updated[i] = { ...updated[i], canonical, selected: !!canonical };
              setMappings(updated);
            }}
            onToggle={(i) => {
              const updated = [...mappings];
              updated[i] = { ...updated[i], selected: !updated[i].selected };
              setMappings(updated);
            }}
            onSelectAll={() =>
              setMappings(mappings.map((m) => ({ ...m, selected: !!m.canonical })))
            }
            onDeselectAll={() =>
              setMappings(mappings.map((m) => ({ ...m, selected: false })))
            }
          />

          {mappings.some((m) => m.selected && m.canonical) && uploadResult.preview.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2">Preview (first {uploadResult.preview.length} rows as they will be imported)</p>
              <div className="border border-gray-200 rounded-lg overflow-hidden text-xs shadow-sm">
                <div className="flex bg-gray-50 px-3 py-2 gap-4 text-gray-500 uppercase tracking-wider font-medium" style={{fontSize: '10px'}}>
                  {mappings.filter((m) => m.selected && m.canonical).map((m) => (
                    <span key={m.canonical} className="flex-1 min-w-0 truncate">{m.canonical!.replace(/_/g, ' ')}</span>
                  ))}
                </div>
                {uploadResult.preview.map((row, ri) => (
                  <div key={ri} className="flex px-3 py-1.5 gap-4 border-t border-gray-100 text-gray-700">
                    {mappings.filter((m) => m.selected && m.canonical).map((m) => (
                      <span key={m.canonical} className="flex-1 min-w-0 truncate">{String(row[m.original] ?? '')}</span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {uploadResult.has_gold_standard && (
            <div className="bg-green-50 border border-green-300 rounded-lg p-4 flex items-center gap-3">
              <input
                type="checkbox"
                checked={importGoldStandard}
                disabled={importing}
                onChange={() => setImportGoldStandard(!importGoldStandard)}
                className="rounded border-green-400"
              />
              <div>
                <p className="text-sm text-green-700">Curation data detected</p>
                <p className="text-xs text-green-600">
                  We found {uploadResult.gold_standard_count} accept/reject
                  records. Import this data to enable the more accurate scoring
                  model.
                </p>
              </div>
            </div>
          )}

          {/* Live status log during import */}
          {(importing || statusMessages.length > 0) && (
            <Card className="border-gray-200 shadow-sm">
              <CardContent className="p-5 space-y-3">
                <div className="space-y-2">
                  {statusMessages.map((msg, i) => {
                    const isActive = i === statusMessages.length - 1 && importing && !importResult;
                    return (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        {isActive ? (
                          <span className="inline-block w-3 h-3 border-2 border-[#cf4520] border-t-transparent rounded-full animate-spin flex-shrink-0" />
                        ) : (
                          <span className="text-green-600 flex-shrink-0">&#10003;</span>
                        )}
                        <span className="text-gray-700">{msg}</span>
                      </div>
                    );
                  })}
                </div>

                {progress && progress.total > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>
                        Batch {progress.batch} of {progress.batches}
                      </span>
                      <span className="tabular-nums">
                        {progress.fetched.toLocaleString()} / {progress.total.toLocaleString()} PMIDs
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded bg-gray-200 overflow-hidden">
                      <div
                        className="h-full bg-[#cf4520] transition-all duration-300"
                        style={{ width: `${fetchPct}%` }}
                      />
                    </div>
                  </div>
                )}

                {batchErrors.length > 0 && (
                  <div className="border border-amber-300 bg-amber-50 rounded p-3">
                    <p className="text-xs font-medium text-amber-700 mb-1">
                      {batchErrors.length} batch{batchErrors.length === 1 ? "" : "es"} had errors (continuing)
                    </p>
                    <ul className="text-xs text-amber-700 list-disc pl-4 space-y-0.5 max-h-24 overflow-y-auto">
                      {batchErrors.map((e, i) => (
                        <li key={i} className="break-words">{e}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {importError && (
                  <div className="border border-red-300 bg-red-50 rounded p-3">
                    <p className="text-sm font-medium text-red-700 mb-1">Import failed</p>
                    <p className="text-xs text-red-600 break-words">{importError}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {!importing && !importResult && (
            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  setUploadResult(null);
                  setMappings([]);
                  setParsingFilename(null);
                  if (replacing) setReplacing(false);
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleImport}
                className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
              >
                Import {uploadResult.row_count} rows
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
    </PrerequisiteGate>
  );
}
