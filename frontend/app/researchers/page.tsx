// frontend/app/researchers/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { ColumnMapper } from "@/components/column-mapper";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { apiUpload, apiFetch } from "@/lib/api";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { useWorkflow } from "@/lib/workflow";

interface Researcher {
  person_id: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  primary_email: string;
  primary_institution: string;
  department: string;
  title: string;
  orcid: string;
  doctoral_year: number;
  article_count: number;
  score_count: number;
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

export default function ResearchersPage() {
  const router = useRouter();
  const { institution, researcherCount, refresh } = useWorkflow();
  const [researchers, setResearchers] = useState<Researcher[] | null>(null);
  const [profileResearcher, setProfileResearcher] = useState<Researcher | null>(null);
  const [replacing, setReplacing] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [importGoldStandard, setImportGoldStandard] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    identity_count: number;
    curation_count: number;
  } | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parsingFilename, setParsingFilename] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [confirmReplace, setConfirmReplace] = useState(false);

  useEffect(() => {
    if (researcherCount > 0 && !replacing && !importResult) {
      apiFetch<Researcher[]>("/api/researchers").then(setResearchers);
    }
  }, [researcherCount, replacing, importResult]);

  useEffect(() => {
    if (importResult) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importResult]);

  async function handleFile(file: File) {
    setParsing(true);
    setParsingFilename(file.name);
    setParseError(null);
    try {
      const result = await apiUpload<UploadResult>("/api/researchers/upload", file);
      setUploadResult(result);
      setMappings(
        result.mappings.map((m) => ({
          ...m,
          selected: !!m.canonical,
        }))
      );
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Failed to parse file");
    } finally {
      setParsing(false);
    }
  }

  async function handleImport() {
    if (!uploadResult) return;
    setImporting(true);
    try {
      const result = await apiFetch<{
        identity_count: number;
        curation_count: number;
      }>("/api/researchers/import", {
        method: "POST",
        body: JSON.stringify({
          file_id: uploadResult.file_id,
          mappings: mappings
            .filter((m) => m.selected && m.canonical)
            .map((m) => ({ original: m.original, canonical: m.canonical })),
          import_gold_standard: importGoldStandard,
        }),
      });
      setImportResult(result);
    } finally {
      setImporting(false);
    }
  }

  // Success state
  if (importResult) {
    return (
      <div className="max-w-2xl">
        <h2 className="text-2xl font-semibold mb-6 text-gray-900">Researchers</h2>
        <Card className="border-green-300 bg-green-50 shadow-sm">
          <CardContent className="p-6 text-center">
            <p className="text-green-700 text-lg font-medium mb-2">
              {importResult.identity_count} researchers loaded
            </p>
            {importResult.curation_count > 0 && (
              <p className="text-green-600 text-sm">
                {importResult.curation_count} curation records imported
              </p>
            )}
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

  // Existing researchers view
  if (researcherCount > 0 && !replacing && !importResult) {
    return (
      <div className="max-w-3xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900">Researchers</h2>
            <p className="text-gray-500 mt-1">{researcherCount} researcher{researcherCount !== 1 ? "s" : ""} loaded</p>
          </div>
          <Button
            variant="outline"
            onClick={() => setConfirmReplace(true)}
          >
            Replace roster
          </Button>
        </div>

        {researchers === null ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : (() => {
          const signals = ["primary_email", "middle_name", "department", "primary_institution", "orcid", "doctoral_year"] as const;
          const signalLabel: Record<string, string> = {
            primary_email: "Email",
            middle_name: "Middle Name",
            department: "Department",
            primary_institution: "Institution",
            orcid: "ORCID",
            doctoral_year: "Year",
          };
          const totalSignals = researchers.length * signals.length;
          const filledSignals = researchers.reduce((sum, r) =>
            sum + signals.filter((s) => s === "doctoral_year" ? r[s] > 0 : !!r[s]).length, 0
          );
          const completeness = totalSignals > 0 ? Math.round((filledSignals / totalSignals) * 100) : 0;

          return (
            <>
              <div className="flex items-center gap-3 mb-4 text-xs text-gray-500">
                <span>Identity completeness:</span>
                <div className="w-32 h-1.5 rounded bg-gray-200 overflow-hidden">
                  <div
                    className={`h-full rounded ${completeness >= 60 ? "bg-green-400" : completeness >= 30 ? "bg-amber-400" : "bg-red-400"}`}
                    style={{ width: `${completeness}%` }}
                  />
                </div>
                <span className="font-medium text-gray-700">{completeness}%</span>
                <span className="text-gray-400">({filledSignals} of {totalSignals} fields populated)</span>
              </div>
              <p className="text-xs text-gray-400 mb-1">Scoring is accurate even with partial identity data. Additional fields improve precision but are not required.</p>
              <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-[10px] font-medium text-gray-500 uppercase tracking-wider">
                      <th className="text-left px-4 py-2 whitespace-nowrap">Name</th>
                      <th className="text-left px-3 py-2 whitespace-nowrap">Person ID</th>
                      {signals.map((s) => (
                        <th key={s} className="text-center px-2 py-2 whitespace-nowrap">{signalLabel[s]}</th>
                      ))}
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                {researchers.map((r) => (
                  <tr
                    key={r.person_id}
                    className="border-t border-gray-100 text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-2 font-medium whitespace-nowrap">{r.last_name}, {r.first_name}</td>
                    <td className="px-3 py-2 text-gray-400 font-mono text-xs whitespace-nowrap">{r.person_id}</td>
                    {signals.map((s) => {
                      const has = s === "doctoral_year" ? r[s] > 0 : !!r[s];
                      return (
                        <td key={s} className="text-center px-2 py-2" title={has ? String(r[s]) : "Missing"}>
                          {has ? (
                            <span className="text-green-500 text-xs">✓</span>
                          ) : (
                            <span className="text-gray-300 text-xs">—</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-3 py-2">
                      <span className="flex gap-2 justify-end whitespace-nowrap">
                      <button
                        onClick={() => setProfileResearcher(r)}
                        className="text-[11px] px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 transition-colors"
                      >
                        Profile
                      </button>
                      {r.score_count > 0 ? (
                        <Link
                          href={`/results/${r.person_id}`}
                          className="text-[11px] px-2 py-1 rounded border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                        >
                          Results
                        </Link>
                      ) : (
                        <span className="text-[11px] px-2 py-1 rounded border border-gray-100 text-gray-300 cursor-default">
                          Results
                        </span>
                      )}
                    </span>
                    </td>
                  </tr>
                ))}
                  </tbody>
                </table>
              </div>
            </>
          );
        })()}

        <ConfirmDialog
          open={confirmReplace}
          onOpenChange={setConfirmReplace}
          title="Upload a new roster?"
          description={
            <p className="text-xs text-gray-500">
              Importing a new file performs a merge, not a clean replace.
            </p>
          }
          preserved={[
            "Existing researchers, scores, curations, and retrieval history",
            "Researchers not listed in the new file (they are NOT removed)",
          ]}
          destroyed={[
            "Identity fields for matching person_ids — overwritten with values from the new file",
          ]}
          confirmLabel="Continue"
          cancelLabel="Stay on roster"
          variant="warning"
          onConfirm={() => setReplacing(true)}
        />

        {/* Profile modal */}
        {profileResearcher && (
          <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={() => setProfileResearcher(null)}>
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">
                  {profileResearcher.first_name} {profileResearcher.last_name}
                </h3>
                <button onClick={() => setProfileResearcher(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
              </div>
              <div className="px-5 py-4 space-y-3">
                {([
                  ["Person ID", profileResearcher.person_id],
                  ["First Name", profileResearcher.first_name],
                  ["Last Name", profileResearcher.last_name],
                  ["Middle Name", profileResearcher.middle_name],
                  ["Email", profileResearcher.primary_email],
                  ["Institution", profileResearcher.primary_institution],
                  ["Department", profileResearcher.department],
                  ["Title", profileResearcher.title],
                  ["ORCID", profileResearcher.orcid],
                  ["Doctoral Year", profileResearcher.doctoral_year > 0 ? String(profileResearcher.doctoral_year) : ""],
                ] as [string, string][]).map(([label, value]) => (
                  <div key={label} className="flex justify-between text-sm">
                    <span className="text-gray-500">{label}</span>
                    <span className={value ? "text-gray-900 font-medium" : "text-gray-300"}>
                      {value || "—"}
                    </span>
                  </div>
                ))}
              </div>
              <div className="px-5 pb-5 pt-2 flex justify-end gap-2">
                {profileResearcher.score_count > 0 && (
                  <Link
                    href={`/results/${profileResearcher.person_id}`}
                    className="text-sm px-3 py-1.5 rounded bg-[#cf4520] text-white hover:bg-[#a3381a] transition-colors"
                  >
                    View Results
                  </Link>
                )}
                <button
                  onClick={() => setProfileResearcher(null)}
                  className="text-sm px-3 py-1.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <PrerequisiteGate
      met={!!institution}
      message="Set up your institution first so the scoring pipeline knows which affiliations to match."
      actionLabel="Go to Institution Setup"
      actionHref="/setup"
    >
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-2xl font-semibold text-gray-900">Researchers</h2>
        {replacing && (
          <Button variant="ghost" size="sm" onClick={() => { setReplacing(false); setUploadResult(null); setMappings([]); }}>
            ← Back to list
          </Button>
        )}
      </div>
      <p className="text-gray-500 mb-6">
        {replacing ? "Upload a new file to replace the current roster." : "Add your faculty and researchers so we can find their publications."}
      </p>

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
            description="Your faculty roster or researcher list — one person per row. At minimum, include a unique ID, first name, and last name. Optional: email, title, primary institution, department, doctoral year, ORCID."
            templateHref="/researcher-template.csv"
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

          {/* Preview of mapped data */}
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

          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              disabled={importing}
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
              disabled={importing}
              className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
            >
              {importing
                ? "Importing..."
                : `Import ${uploadResult.row_count} Researchers`}
            </Button>
          </div>
        </div>
      )}
    </div>
    </PrerequisiteGate>
  );
}
