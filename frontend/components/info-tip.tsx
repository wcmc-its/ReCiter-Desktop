"use client";

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex items-center ml-1">
      <span className="w-4 h-4 rounded-full bg-gray-200 text-gray-500 text-[10px] inline-flex items-center justify-center cursor-help">?</span>
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg whitespace-normal w-64 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-10 shadow-lg">
        {text}
      </span>
    </span>
  );
}
