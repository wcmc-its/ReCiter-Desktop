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
  disabled?: boolean;
  availableFields?: string[];
}

const DEFAULT_AVAILABLE_FIELDS = [
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
  disabled = false,
  availableFields = DEFAULT_AVAILABLE_FIELDS,
}: ColumnMapperProps) {
  return (
    <div className={disabled ? "opacity-60 pointer-events-none" : undefined} aria-disabled={disabled}>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-600">
          We detected <strong className="text-gray-900">{mappings.length} columns</strong> in
          your file. Please confirm the mappings below.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onSelectAll} disabled={disabled}>
            Select All
          </Button>
          <Button variant="outline" size="sm" onClick={onDeselectAll} disabled={disabled}>
            Deselect All
          </Button>
        </div>
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        {/* Header */}
        <div className="grid grid-cols-[40px_180px_30px_200px_140px] gap-2 items-center px-4 py-2 bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
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
            className={`grid grid-cols-[40px_180px_30px_200px_140px] gap-2 items-center px-4 py-3 border-t border-gray-200 bg-white ${
              !m.canonical ? "bg-amber-50" : ""
            }`}
          >
            <div className="flex justify-center">
              <input
                type="checkbox"
                checked={m.selected && !!m.canonical}
                onChange={() => onToggle(i)}
                className="rounded border-gray-300"
                disabled={disabled || !m.canonical}
              />
            </div>
            <code className="text-sm text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
              {m.original}
            </code>
            <span className="text-gray-400 text-center">{"\u2192"}</span>
            <select
              className={
                m.canonical
                  ? "bg-white text-green-700 border border-gray-200 rounded px-2 py-1 text-sm disabled:opacity-50"
                  : "bg-white text-amber-700 border border-amber-300 rounded px-2 py-1 text-sm disabled:opacity-50"
              }
              value={m.canonical ?? ""}
              disabled={disabled}
              onChange={(e) => {
                const v = e.target.value;
                // "__skip" and "" both clear the canonical mapping. Storing
                // "__skip" verbatim would create a junk dataframe column.
                onMappingChange(i, v === "" || v === "__skip" ? null : v);
              }}
            >
              <option value="">-- Select mapping --</option>
              {availableFields.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
              <option value="__skip">Skip this column</option>
            </select>
            <span className="text-xs text-gray-400 font-mono truncate">
              {m.sample}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
