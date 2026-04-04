// frontend/components/score-badge.tsx
export function ScoreBadge({ score }: { score: number }) {
  let bg: string;
  let text: string;
  if (score >= 95) {
    bg = "bg-green-50";
    text = "text-green-700";
  } else if (score >= 10) {
    bg = "bg-amber-50";
    text = "text-amber-700";
  } else {
    bg = "bg-red-50";
    text = "text-red-600";
  }
  return (
    <span
      className={`inline-block w-12 text-center py-1 rounded text-sm font-semibold ${bg} ${text}`}
    >
      {score}
    </span>
  );
}
