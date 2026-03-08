import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { AccuracyDistribution, AccuracyBucket } from "../../types";
import { getAccuracyDistribution } from "../../api/signals";
import LoadingSkeleton from "../common/LoadingSkeleton";
import ErrorRetry from "../common/ErrorRetry";

export default function AccuracyDistributionChart() {
  const [windowDays, setWindowDays] = useState(5);

  const { data, isLoading, error, refetch } = useQuery<AccuracyDistribution>({
    queryKey: ["accuracy-distribution", windowDays],
    queryFn: () => getAccuracyDistribution({ window_days: windowDays }),
  });

  if (isLoading) return <LoadingSkeleton variant="row" count={4} />;
  if (error) return <ErrorRetry message="Failed to load accuracy distribution" onRetry={refetch} />;

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-4">
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

      {!data || (data.by_strength.length === 0 && data.by_direction.length === 0) ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No accuracy distribution data available.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <BucketGroup title="By Strength" buckets={data.by_strength} />
          <BucketGroup title="By Direction" buckets={data.by_direction} />
        </div>
      )}
    </div>
  );
}

function BucketGroup({ title, buckets }: { title: string; buckets: AccuracyBucket[] }) {
  if (buckets.length === 0) return null;

  return (
    <div>
      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{title}</h4>
      <div className="space-y-3">
        {buckets.map((bucket) => {
          const isGood = bucket.accuracy_pct >= 50;
          const barWidth = Math.min(bucket.accuracy_pct, 100);

          return (
            <div key={bucket.label}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                  {bucket.label}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {bucket.correct}/{bucket.total} signals
                </span>
              </div>
              <div className="h-6 bg-gray-100 dark:bg-gray-700 rounded relative">
                <div
                  className={`h-full rounded ${isGood ? "bg-emerald-500" : "bg-red-500"}`}
                  style={{ width: `${barWidth}%` }}
                />
                <div
                  className="absolute top-0 h-full w-px bg-gray-400 dark:bg-gray-500"
                  style={{ left: "50%" }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-xs font-semibold text-gray-800 dark:text-gray-100">
                  {bucket.accuracy_pct.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Avg return: {bucket.avg_return_pct >= 0 ? "+" : ""}{bucket.avg_return_pct.toFixed(2)}%
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
