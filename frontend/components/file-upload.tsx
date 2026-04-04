// frontend/components/file-upload.tsx
"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";

interface FileUploadProps {
  onFileSelected: (file: File) => void;
  description: string;
  accept?: string;
}

export function FileUpload({ onFileSelected, description, accept }: FileUploadProps) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFileSelected(file);
    },
    [onFileSelected]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors bg-white ${
        dragging ? "border-[#cf4520] bg-[#cf4520]/5" : "border-gray-300"
      }`}
    >
      <p className="text-lg text-gray-800 mb-2 font-medium">
        Upload your researcher list
      </p>
      <p className="text-sm text-gray-500 mb-1 max-w-md mx-auto leading-relaxed">
        {description}
      </p>
      <p className="text-xs text-gray-400 mb-5">CSV, Excel (.xlsx, .xls), or TSV</p>
      <div className="flex items-center justify-center gap-3">
        <Button
          variant="default"
          className="bg-[#cf4520] hover:bg-[#a3381a] text-white"
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = accept || ".csv,.xlsx,.xls,.tsv";
            input.onchange = (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) onFileSelected(file);
            };
            input.click();
          }}
        >
          Browse files
        </Button>
        <span className="text-gray-400 text-sm">or</span>
        <a href="#" className="text-sm text-[#cf4520] border-b border-dashed border-[#cf4520]/30">
          Download sample template
        </a>
      </div>
      <p className="text-xs text-gray-400 mt-4">
        Column names are flexible — we recognize many common variations.
      </p>
    </div>
  );
}
