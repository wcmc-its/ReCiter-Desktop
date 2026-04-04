// frontend/app/researchers/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { ColumnMapper } from "@/components/column-mapper";
import { apiUpload, apiFetch } from "@/lib/api";

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
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [importGoldStandard, setImportGoldStandard] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    identity_count: number;
    curation_count: number;
  } | null>(null);

  async function handleFile(file: File) {
    const result = await apiUpload<UploadResult>("/api/researchers/upload", file);
    setUploadResult(result);
    setMappings(
      result.mappings.map((m) => ({
        ...m,
        selected: !!m.canonical,
      }))
    );
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
              Continue to Pipeline
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2 text-gray-900">Researchers</h2>
      <p className="text-gray-500 mb-6">
        Upload your researcher list to get started.
      </p>

      {!uploadResult ? (
        <FileUpload
          onFileSelected={handleFile}
          description="A spreadsheet with one row per researcher. At minimum, include a unique ID, first name, and last name. Optional: email, title, primary institution, department, doctoral year, ORCID."
        />
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {uploadResult.filename} — {uploadResult.row_count} rows
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setUploadResult(null);
                setMappings([]);
              }}
            >
              Upload different file
            </Button>
          </div>

          <ColumnMapper
            mappings={mappings}
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

          {uploadResult.has_gold_standard && (
            <div className="bg-green-50 border border-green-300 rounded-lg p-4 flex items-center gap-3">
              <input
                type="checkbox"
                checked={importGoldStandard}
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
              onClick={() => {
                setUploadResult(null);
                setMappings([]);
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
  );
}
