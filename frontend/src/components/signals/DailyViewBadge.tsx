import { DIRECTION_COLORS } from "../../constants/ui";

interface DailyViewBadgeProps {
  direction: string;
  conviction: number;
}

export function ConvictionBar({ value }: { value: number }) {
  const clamped = Math.min(1, Math.max(0, value));
  const filled = Math.round(clamped * 5);
  return (
    <span className="font-mono text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
      {"█".repeat(filled)}
      {"░".repeat(5 - filled)} {clamped.toFixed(2)}
    </span>
  );
}

export function DirectionChip({ direction }: { direction: string }) {
  const dir = DIRECTION_COLORS[direction] ?? DIRECTION_COLORS.neutral!;
  const arrow = direction === "bearish" ? "▼" : direction === "bullish" ? "▲" : "●";
  const label = direction.charAt(0).toUpperCase() + direction.slice(1);
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${dir.bg} ${dir.text}`}>
      {arrow} {label}
    </span>
  );
}

export default function DailyViewBadge({ direction, conviction }: DailyViewBadgeProps) {
  return (
    <span className="inline-flex items-center gap-2">
      <DirectionChip direction={direction} />
      <ConvictionBar value={conviction} />
    </span>
  );
}
