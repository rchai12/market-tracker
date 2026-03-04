import { Link } from "react-router-dom";
import type { Signal } from "../../types";

interface TopMoversCardProps {
  signal: Signal;
  rank: number;
}

const DIRECTION_COLORS: Record<string, { bg: string; text: string }> = {
  bullish: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400" },
  bearish: { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400" },
  neutral: { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-600 dark:text-gray-300" },
};

export default function TopMoversCard({ signal, rank }: TopMoversCardProps) {
  const dir = DIRECTION_COLORS[signal.direction] || DIRECTION_COLORS.neutral;

  return (
    <div className="flex items-center gap-3 py-2 border-b border-gray-100 dark:border-gray-700/50 last:border-b-0">
      <span className="text-xs text-gray-400 dark:text-gray-500 w-5 text-right">
        #{rank}
      </span>
      <Link
        to={`/stocks/${signal.ticker}`}
        className="font-semibold text-sm text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 w-14"
      >
        {signal.ticker}
      </Link>
      <span className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1">
        {signal.company_name}
      </span>
      <span className="text-xs font-mono text-gray-700 dark:text-gray-300 w-12 text-right">
        {signal.composite_score.toFixed(3)}
      </span>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${dir.bg} ${dir.text}`}>
        {signal.direction}
      </span>
    </div>
  );
}
