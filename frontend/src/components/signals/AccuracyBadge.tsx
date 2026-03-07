interface AccuracyBadgeProps {
  accuracy: number;
  size?: "sm" | "md";
}

function getAccuracyColors(accuracy: number): { bg: string; text: string } {
  if (accuracy >= 60) return { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400" };
  if (accuracy >= 50) return { bg: "bg-yellow-100 dark:bg-yellow-900/30", text: "text-yellow-700 dark:text-yellow-400" };
  return { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400" };
}

export default function AccuracyBadge({ accuracy, size = "sm" }: AccuracyBadgeProps) {
  const colors = getAccuracyColors(accuracy);
  const sizeClasses = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${colors.bg} ${colors.text} ${sizeClasses}`}>
      {accuracy.toFixed(1)}% accurate
    </span>
  );
}
