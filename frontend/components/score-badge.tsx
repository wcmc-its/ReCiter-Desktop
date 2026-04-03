// frontend/components/score-badge.tsx
export function ScoreBadge({ score }: { score: number }) {
  let bg: string;
  let text: string;
  if (score >= 70) {
    bg = "bg-green-900/60";
    text = "text-green-400";
  } else if (score >= 30) {
    bg = "bg-amber-900/40";
    text = "text-amber-400";
  } else {
    bg = "bg-red-900/40";
    text = "text-red-400";
  }
  return (
    <span
      className={`inline-block w-12 text-center py-1 rounded text-sm font-semibold ${bg} ${text}`}
    >
      {score}
    </span>
  );
}
