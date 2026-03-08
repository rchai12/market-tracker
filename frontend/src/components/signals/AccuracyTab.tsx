import { useQuery } from "@tanstack/react-query";
import { getSignalAccuracy } from "../../api/signals";
import { listSectors } from "../../api/stocks";
import AccuracyTrendChart from "./AccuracyTrendChart";
import AccuracyDistributionChart from "./AccuracyDistributionChart";
import Card from "../common/Card";

export default function AccuracyTab() {
  const { data: sectors } = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
    staleTime: 5 * 60 * 1000,
  });

  const { data: accuracyData } = useQuery({
    queryKey: ["signal-accuracy-summary"],
    queryFn: () => getSignalAccuracy({ window_days: 5 }),
  });

  return (
    <div className="space-y-8">
      {/* Summary */}
      {accuracyData && accuracyData.length > 0 && (() => {
        const summary = accuracyData[0]!;
        return (
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Overall Accuracy (5-Day Window)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {summary.accuracy_pct.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Overall</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {summary.total_evaluated}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Evaluated</p>
            </div>
            {summary.bullish_accuracy_pct != null && (
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                  {summary.bullish_accuracy_pct.toFixed(1)}%
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Bullish</p>
              </div>
            )}
            {summary.bearish_accuracy_pct != null && (
              <div className="text-center">
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {summary.bearish_accuracy_pct.toFixed(1)}%
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Bearish</p>
              </div>
            )}
          </div>
        </Card>
        );
      })()}

      {/* Trend */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Accuracy Trend
        </h2>
        <AccuracyTrendChart sectors={sectors} />
      </Card>

      {/* Distribution */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Accuracy Distribution
        </h2>
        <AccuracyDistributionChart />
      </Card>
    </div>
  );
}
