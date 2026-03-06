interface SentimentBadgeProps {
  label: string;
  score?: number;
  size?: "sm" | "md";
}

const COLORS: Record<string, { bg: string; text: string }> = {
  positive: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400" },
  negative: { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400" },
  neutral: { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-600 dark:text-gray-300" },
};

export default function SentimentBadge({ label, score, size = "sm" }: SentimentBadgeProps) {
  const colors = COLORS[label] ?? COLORS.neutral!;
  const sizeClasses = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium ${colors.bg} ${colors.text} ${sizeClasses}`}>
      {label}
      {score !== undefined && (
        <span className="opacity-75">({(score * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
