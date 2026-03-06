import { Link } from "react-router-dom";
import type { Signal } from "../../types";
import { DIRECTION_COLORS, STRENGTH_STYLES } from "../../constants/ui";
import { formatTimeAgo } from "../../utils/format";

interface SignalCardProps {
  signal: Signal;
}

export default function SignalCard({ signal }: SignalCardProps) {
  const dirColors = DIRECTION_COLORS[signal.direction] ?? DIRECTION_COLORS.neutral!;
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
