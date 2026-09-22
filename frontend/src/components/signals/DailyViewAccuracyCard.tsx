import type { DailyViewAccuracySummary } from "../../types";

interface DailyViewAccuracyCardProps {
  summary: DailyViewAccuracySummary;
  title?: string;
}

function formatAlpha(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function accumulatingMessage(summary: DailyViewAccuracySummary): string {
  return `Evaluated ${summary.evaluated_views} of ~${summary.min_views_for_confidence} views needed for reliable accuracy metrics`;
}

export default function DailyViewAccuracyCard({
  summary,
  title = "Daily View Accuracy (last 90 days)",
}: DailyViewAccuracyCardProps) {
  if (summary.insufficient_data) {
    const pct = Math.min(
      100,
      (summary.evaluated_views / Math.max(summary.min_views_for_confidence, 1)) * 100
    );
    return (
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">{title}</h2>
        <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">Building accuracy history...</p>
        <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden mb-2">
          <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">{accumulatingMessage(summary)}</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{title}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="text-center rounded-lg bg-gray-50 dark:bg-gray-700/40 p-4">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {summary.accuracy_pct.toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Accuracy</p>
        </div>
        <div className="text-center rounded-lg bg-gray-50 dark:bg-gray-700/40 p-4">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {formatAlpha(summary.avg_excess_return_all)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Avg α</p>
        </div>
        <div className="text-center rounded-lg bg-gray-50 dark:bg-gray-700/40 p-4">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.evaluated_views}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Views</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-gray-500 dark:text-gray-400 text-center">
        Correct {summary.correct} / {summary.evaluated_views}
        {" · "}
        avg α when right {formatAlpha(summary.avg_excess_return_correct)}
        {" · "}
        when wrong {formatAlpha(summary.avg_excess_return_incorrect)}
      </p>
    </div>
  );
}
