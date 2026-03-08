import { useState } from "react";
import { Link } from "react-router-dom";
import type { Signal } from "../../types";
import { DIRECTION_COLORS, STRENGTH_STYLES } from "../../constants/ui";
import { formatTimeAgo } from "../../utils/format";
import ComponentBreakdown from "./ComponentBreakdown";

interface SignalCardProps {
  signal: Signal;
  onDetailClick?: (signal: Signal) => void;
}

export default function SignalCard({ signal, onDetailClick }: SignalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const dirColors = DIRECTION_COLORS[signal.direction] ?? DIRECTION_COLORS.neutral!;
  const strengthStyle = STRENGTH_STYLES[signal.strength] || "";
  const timeAgo = formatTimeAgo(signal.generated_at);

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow p-4 ${strengthStyle}`}>
      <Link
        to={`/stocks/${signal.ticker}`}
        className="block hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-lg font-semibold text-gray-900 dark:text-white">
            {signal.ticker}
          </span>
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

        {signal.ml_score != null && (
          <div className="flex items-center gap-2 text-xs mt-1 py-1.5 px-2 bg-purple-50 dark:bg-purple-900/20 rounded">
            <span className="text-purple-600 dark:text-purple-400 font-medium">ML</span>
            <span className={`font-mono ${signal.ml_direction === "bullish" ? "text-emerald-600 dark:text-emerald-400" : signal.ml_direction === "bearish" ? "text-red-600 dark:text-red-400" : "text-gray-500"}`}>
              {signal.ml_score > 0 ? "+" : ""}{signal.ml_score.toFixed(3)}
            </span>
            {signal.ml_confidence != null && (
              <span className="text-gray-400">({(signal.ml_confidence * 100).toFixed(0)}%)</span>
            )}
            {signal.ml_direction && signal.ml_direction !== signal.direction && (
              <span className="text-amber-500 dark:text-amber-400 text-[10px] font-medium">DISAGREES</span>
            )}
          </div>
        )}
      </Link>

      <div className="flex items-center justify-between mt-1">
        <p className="text-xs text-gray-400 dark:text-gray-500">{timeAgo}</p>
        <div className="flex items-center gap-2">
          {onDetailClick && (
            <button
              onClick={() => onDetailClick(signal)}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
            >
              Details
            </button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            title={expanded ? "Collapse" : "Show breakdown"}
          >
            <svg
              className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {expanded && <ComponentBreakdown signal={signal} />}
    </div>
  );
}
