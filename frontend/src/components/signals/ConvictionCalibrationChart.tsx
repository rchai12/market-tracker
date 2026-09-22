import type { DailyViewCalibrationBucket } from "../../types";

interface ConvictionCalibrationChartProps {
  buckets: DailyViewCalibrationBucket[];
}

const MIN_BUCKET = 10;

export function calibrationIsThin(buckets: DailyViewCalibrationBucket[], minCount = MIN_BUCKET): boolean {
  return buckets.length === 0 || buckets.some((b) => b.count < minCount);
}

export default function ConvictionCalibrationChart({ buckets }: ConvictionCalibrationChartProps) {
  if (calibrationIsThin(buckets)) {
    const n = buckets.reduce((sum, b) => sum + b.count, 0);
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
        Conviction calibration needs at least {MIN_BUCKET} views in every bucket.
        {n > 0 ? ` ${n} evaluated so far.` : ""}
      </p>
    );
  }

  const maxAcc = Math.max(100, ...buckets.map((b) => b.accuracy_pct));

  return (
    <div>
      <div className="flex items-end gap-3 h-48">
        {buckets.map((bucket) => {
          const height = (bucket.accuracy_pct / maxAcc) * 100;
          const good = bucket.accuracy_pct >= 50;
          return (
            <div key={bucket.label} className="flex-1 flex flex-col items-center h-full">
              <div className="relative flex-1 w-full flex items-end">
                <div className="absolute left-0 right-0 border-t border-dashed border-gray-400 dark:border-gray-500" style={{ bottom: `${(50 / maxAcc) * 100}%` }} />
                <div
                  className={`w-full rounded-t ${good ? "bg-emerald-500/80" : "bg-red-500/70"}`}
                  style={{ height: `${height}%` }}
                  title={`${bucket.label}: ${bucket.accuracy_pct.toFixed(1)}% (n=${bucket.count})`}
                />
              </div>
              <p className="mt-2 text-xs font-medium text-gray-700 dark:text-gray-300">{bucket.label}</p>
              <p className={`text-xs font-mono ${good ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                {bucket.accuracy_pct.toFixed(1)}%
              </p>
              <p className="text-[10px] text-gray-400">n={bucket.count}</p>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] text-gray-400 dark:text-gray-500 text-center">
        Dashed line is 50%. Higher conviction should be more accurate if the system is calibrated.
      </p>
    </div>
  );
}
