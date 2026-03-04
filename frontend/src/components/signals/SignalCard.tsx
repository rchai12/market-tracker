import { Link } from "react-router-dom";
import type { Signal } from "../../types";

interface SignalCardProps {
  signal: Signal;
}

const DIRECTION_COLORS: Record<string, { bg: string; text: string }> = {
  bullish: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400" },
  bearish: { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400" },
  neutral: { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-600 dark:text-gray-300" },
};

const STRENGTH_STYLES: Record<string, string> = {
  strong: "border-l-4 border-l-yellow-500",
  moderate: "border-l-4 border-l-blue-400",
  weak: "border-l-2 border-l-gray-300 dark:border-l-gray-600",
};

export default function SignalCard({ signal }: SignalCardProps) {
  const dirColors = DIRECTION_COLORS[signal.direction] || DIRECTION_COLORS.neutral;
  const strengthStyle = STRENGTH_STYLES[signal.strength] || "";
  const timeAgo = formatTimeAgo(signal.generated_at);

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow p-4 ${strengthStyle}`}>
      <div className="flex items-center justify-between mb-2">
        <Link
          to={`/stocks/${signal.ticker}`}
          className="text-lg font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400"
        >
          {signal.ticker}
        </Link>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${dirColors.bg} ${dirColors.text}`}>
          {signal.direction}
        </span>
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">{signal.company_name}</p>

      <div className="grid grid-cols-3 gap-2 text-sm mb-3">
        <div className="text-center">
          <p className="font-semibold text-gray-900 dark:text-white">
            {signal.composite_score.toFixed(3)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Score</p>
        </div>
        <div className="text-center">
          <p className="font-semibold text-gray-900 dark:text-white capitalize">
            {signal.strength}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Strength</p>
        </div>
        <div className="text-center">
          <p className="font-semibold text-gray-900 dark:text-white">
            {signal.article_count}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Articles</p>
        </div>
      </div>

      {signal.reasoning && (
        <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2 mb-2">
          {signal.reasoning}
        </p>
      )}

      <p className="text-xs text-gray-400 dark:text-gray-500">{timeAgo}</p>
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
