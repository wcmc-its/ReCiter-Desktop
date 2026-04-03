// frontend/components/column-mapper.tsx
"use client";

import { Button } from "@/components/ui/button";

interface Mapping {
  original: string;
  canonical: string | null;
  sample: string;
  selected: boolean;
}

interface ColumnMapperProps {
  mappings: Mapping[];
  onMappingChange: (index: number, canonical: string | null) => void;
  onToggle: (index: number) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

const AVAILABLE_FIELDS = [
  "person_id", "first_name", "last_name", "middle_name",
  "primary_email", "primary_institution", "department", "title",
  "orcid", "bachelor_year", "doctoral_year", "pmid", "assertion",
];

export function ColumnMapper({
  mappings,
  onMappingChange,
  onToggle,
  onSelectAll,
  onDeselectAll,
}: ColumnMapperProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-400">
          We detected <strong className="text-gray-200">{mappings.length} columns</strong> in
          your file. Please confirm the mappings below.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onSelectAll}>
            Select All
          </Button>
          <Button variant="outline" size="sm" onClick={onDeselectAll}>
            Deselect All
          </Button>
        </div>
      </div>

      <div className="border border-gray-800 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[40px_180px_30px_200px_140px] gap-2 items-center px-4 py-2 bg-gray-900 text-xs text-gray-500 uppercase tracking-wider">
          <span />
          <span>Your Column</span>
          <span />
          <span>Maps To</span>
          <span>Sample</span>
        </div>

        {/* Rows */}
        {mappings.map((m, i) => (
          <div
            key={i}
            className={`grid grid-cols-[40px_180px_30px_200px_140px] gap-2 items-center px-4 py-3 border-t border-gray-800 ${
              !m.canonical ? "bg-amber-950/10" : ""
            }`}
          >
            <div className="flex justify-center">
              <input
                type="checkbox"
                checked={m.selected && !!m.canonical}
                onChange={() => onToggle(i)}
                className="rounded border-gray-600"
                disabled={!m.canonical}
              />
            </div>
            <code className="text-sm text-gray-300 bg-gray-800 px-2 py-0.5 rounded">
              {m.original}
            </code>
            <span className="text-gray-600 text-center">{"\u2192"}</span>
            {m.canonical ? (
              <span className="text-sm text-green-400">{m.canonical}</span>
            ) : (
              <select
                className="bg-gray-800 text-amber-400 border border-amber-800/30 rounded px-2 py-1 text-sm"
                value=""
                onChange={(e) =>
                  onMappingChange(i, e.target.value || null)
                }
              >
                <option value="">-- Select mapping --</option>
                {AVAILABLE_FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
                <option value="__skip">Skip this column</option>
              </select>
            )}
            <span className="text-xs text-gray-600 font-mono truncate">
              {m.sample}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
