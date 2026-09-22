import { useQuery } from "@tanstack/react-query";
import {
  getDailyViewAccuracy,
  getDailyViewCalibration,
  isoDateDaysAgo,
} from "../../api/signals";
import AccuracyBadge from "../signals/AccuracyBadge";
import LoadingSkeleton from "../common/LoadingSkeleton";
import ErrorRetry from "../common/ErrorRetry";
import { accumulatingMessage } from "../signals/DailyViewAccuracyCard";

const LOOKBACK_DAYS = 30;
const DOT_LABELS = ["Low", "Medium", "High"] as const;

function dotClass(accuracy: number | null): string {
  if (accuracy == null) return "bg-gray-300 dark:bg-gray-600";
  if (accuracy >= 55) return "bg-emerald-500";
  if (accuracy >= 50) return "bg-yellow-400";
  return "bg-red-500";
}

function formatAlpha(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export default function AccuracyCard() {
  const params = { window_days: 1, date_from: isoDateDaysAgo(LOOKBACK_DAYS) };
  const summaryQuery = useQuery({
    queryKey: ["daily-view-accuracy", params],
    queryFn: () => getDailyViewAccuracy(params),
  });
  const calibrationQuery = useQuery({
    queryKey: ["daily-view-calibration", params],
    queryFn: () => getDailyViewCalibration(params),
  });

  if (summaryQuery.isLoading || calibrationQuery.isLoading) {
    return <LoadingSkeleton variant="row" count={2} />;
  }
  if (summaryQuery.isError) {
    return <ErrorRetry onRetry={() => summaryQuery.refetch()} />;
  }

  const summary = summaryQuery.data;
  if (!summary) {
    return (
      <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
        No accuracy data yet. Data will appear after daily views are evaluated.
      </p>
    );
  }

  if (summary.insufficient_data) {
    const pct = Math.min(
      100,
      (summary.evaluated_views / Math.max(summary.min_views_for_confidence, 1)) * 100
    );
    return (
      <div>
        <p className="text-sm text-gray-700 dark:text-gray-200 mb-2">Building accuracy history...</p>
        <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden mb-2">
          <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">{accumulatingMessage(summary)}</p>
      </div>
    );
  }

  const byLabel = new Map(
    (calibrationQuery.data?.buckets ?? []).map((b) => [b.label, b.accuracy_pct] as const)
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {summary.accuracy_pct.toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {summary.evaluated_views} daily views · 1-day excess return · {LOOKBACK_DAYS}d
          </p>
        </div>
        <AccuracyBadge accuracy={summary.accuracy_pct} size="md" />
      </div>

      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          Avg α {formatAlpha(summary.avg_excess_return_all)}
        </p>
        <div className="flex items-center gap-2" title="Low / Medium / High conviction accuracy">
          {DOT_LABELS.map((label) => (
            <span key={label} className="flex items-center gap-1">
              <span className={`h-2.5 w-2.5 rounded-full ${dotClass(byLabel.get(label) ?? null)}`} />
              <span className="text-[10px] text-gray-400">{label[0]}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
