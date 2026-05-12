"use client";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatusCardProps {
  stepNumber: number;
  label: string;
  value: string;
  isComplete: boolean;
  isNext: boolean;
}

export function StatusCard({ stepNumber, label, value, isComplete, isNext }: StatusCardProps) {
  return (
    <Card
      className={cn(
        "transition-colors border shadow-sm",
        isNext && "border-[#cf4520] bg-[#cf4520]/5",
        isComplete && "border-green-300",
        !isNext && !isComplete && "border-gray-200"
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <div
            className={cn(
              "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0",
              isComplete
                ? "bg-green-600 text-white"
                : isNext
                ? "bg-[#cf4520] text-white"
                : "bg-gray-200 text-gray-500"
            )}
          >
            {isComplete ? "\u2713" : stepNumber}
          </div>
          <span className="text-xs text-gray-500 uppercase tracking-wider">
            {label}
          </span>
        </div>
        <p
          className={cn(
            "text-sm font-medium ml-7",
            isComplete ? "text-green-600" : isNext ? "text-[#cf4520]" : "text-gray-400"
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
