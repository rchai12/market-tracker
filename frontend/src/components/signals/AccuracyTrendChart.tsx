import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { AccuracyTrendPoint } from "../../types";
import { getAccuracyTrend } from "../../api/signals";
import LoadingSkeleton from "../common/LoadingSkeleton";
import ErrorRetry from "../common/ErrorRetry";

interface AccuracyTrendChartProps {
  sectors?: string[];
}

export default function AccuracyTrendChart({ sectors }: AccuracyTrendChartProps) {
  const [windowDays, setWindowDays] = useState(5);
  const [sector, setSector] = useState<string | undefined>();
  const [bucket, setBucket] = useState<"week" | "month">("week");

  const { data, isLoading, error, refetch } = useQuery<AccuracyTrendPoint[]>({
    queryKey: ["accuracy-trend", windowDays, sector, bucket],
    queryFn: () => getAccuracyTrend({ window_days: windowDays, sector, bucket }),
  });

  if (isLoading) return <LoadingSkeleton variant="row" count={4} />;
  if (error) return <ErrorRetry message="Failed to load accuracy trend" onRetry={refetch} />;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 dark:text-gray-400">Window:</label>
          {[1, 3, 5].map((w) => (
            <button
              key={w}
              onClick={() => setWindowDays(w)}
              className={`px-2 py-0.5 text-xs rounded ${
                windowDays === w
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
              }`}
            >
              {w}d
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 dark:text-gray-400">Bucket:</label>
          {(["week", "month"] as const).map((b) => (
            <button
              key={b}
              onClick={() => setBucket(b)}
              className={`px-2 py-0.5 text-xs rounded capitalize ${
                bucket === b
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
              }`}
            >
              {b}
            </button>
          ))}
        </div>
        {sectors && sectors.length > 0 && (
          <select
            value={sector ?? ""}
            onChange={(e) => setSector(e.target.value || undefined)}
            className="text-xs border rounded px-2 py-1 bg-white dark:bg-gray-700 dark:border-gray-600 text-gray-900 dark:text-white"
          >
            <option value="">All Sectors</option>
            {sectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}
      </div>

      {!data || data.length === 0 ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No accuracy data available for the selected filters.
        </div>
      ) : (
        <div className="space-y-1">
          {data.map((point, i) => {
            const dateLabel = new Date(point.period_start).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            });
            const barWidth = (point.accuracy_pct / 100) * 100;
            const isGood = point.accuracy_pct >= 50;

            return (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-16 text-gray-500 dark:text-gray-400 shrink-0">{dateLabel}</span>
                <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded relative">
                  <div
                    className={`h-full rounded ${isGood ? "bg-emerald-500/70" : "bg-red-500/70"}`}
                    style={{ width: `${barWidth}%` }}
                  />
                  <div
                    className="absolute top-0 h-full w-px bg-gray-400 dark:bg-gray-500"
                    style={{ left: "50%" }}
                  />
                </div>
                <span className={`w-12 text-right font-mono ${isGood ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                  {point.accuracy_pct.toFixed(0)}%
                </span>
                <span className="w-10 text-right text-gray-400 dark:text-gray-500">
                  n={point.total}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
