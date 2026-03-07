import type { SignalAccuracy } from "../../types";
import AccuracyBadge from "../signals/AccuracyBadge";

interface AccuracyCardProps {
  data: SignalAccuracy[];
}

export default function AccuracyCard({ data }: AccuracyCardProps) {
  // Find the 5-day global/overall entry as primary, fall back to first
  const primary = data.find((d) => d.window_days === 5) ?? data[0];

  if (!primary) {
    return (
      <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
        No accuracy data yet. Data will appear after signal outcomes are evaluated.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {primary.accuracy_pct.toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {primary.total_evaluated} signals evaluated ({primary.window_days}-day window)
          </p>
        </div>
        <AccuracyBadge accuracy={primary.accuracy_pct} size="md" />
      </div>

      {(primary.bullish_accuracy_pct !== null || primary.bearish_accuracy_pct !== null) && (
        <div className="grid grid-cols-2 gap-3 mb-3">
          {primary.bullish_accuracy_pct !== null && (
            <div className="text-center rounded-lg bg-green-50 dark:bg-green-900/20 p-2">
              <p className="text-lg font-semibold text-green-700 dark:text-green-400">
                {primary.bullish_accuracy_pct.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Bullish</p>
            </div>
          )}
          {primary.bearish_accuracy_pct !== null && (
            <div className="text-center rounded-lg bg-red-50 dark:bg-red-900/20 p-2">
              <p className="text-lg font-semibold text-red-700 dark:text-red-400">
                {primary.bearish_accuracy_pct.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Bearish</p>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="text-center">
          <p className="font-semibold text-green-600 dark:text-green-400">
            {primary.avg_return_correct >= 0 ? "+" : ""}{primary.avg_return_correct.toFixed(2)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Avg Return (Correct)</p>
        </div>
        <div className="text-center">
          <p className="font-semibold text-red-600 dark:text-red-400">
            {primary.avg_return_wrong >= 0 ? "+" : ""}{primary.avg_return_wrong.toFixed(2)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Avg Return (Wrong)</p>
        </div>
      </div>
    </div>
  );
}
