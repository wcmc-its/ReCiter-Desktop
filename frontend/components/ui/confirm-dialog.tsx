"use client";

import { ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  preserved?: ReactNode[];
  destroyed?: ReactNode[];
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning";
  onConfirm: () => void;
  confirmDisabled?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  preserved,
  destroyed,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  onConfirm,
  confirmDisabled = false,
}: ConfirmDialogProps) {
  if (!open) return null;

  const confirmClass =
    variant === "danger"
      ? "bg-red-600 hover:bg-red-700 text-white"
      : "bg-amber-600 hover:bg-amber-700 text-white";

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <div className="px-5 pt-5 pb-3 border-b border-gray-200">
          <h3 id="confirm-dialog-title" className="text-lg font-semibold text-gray-900">
            {title}
          </h3>
        </div>
        <div className="px-5 py-4 text-sm text-gray-700 space-y-2">
          {description && <div>{description}</div>}
          {preserved && preserved.length > 0 && (
            <div>
              <p className="font-medium text-green-700 mb-1">Preserved</p>
              <ul className="list-disc list-inside text-gray-700 space-y-0.5">
                {preserved.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          {destroyed && destroyed.length > 0 && (
            <div>
              <p className="font-medium text-red-700 mb-1">Discarded</p>
              <ul className="list-disc list-inside text-gray-700 space-y-0.5">
                {destroyed.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="px-5 pb-5 pt-2 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button
            size="sm"
            className={confirmClass}
            disabled={confirmDisabled}
            onClick={() => {
              onOpenChange(false);
              onConfirm();
            }}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
