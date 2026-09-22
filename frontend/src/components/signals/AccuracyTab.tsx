import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  getDailyViewAccuracy,
  getDailyViewAccuracyTrend,
  getDailyViewCalibration,
  getDailyViewRegimeAccuracy,
  getDailyViewSectorAccuracy,
  getMLAccuracy,
  getSignalAccuracy,
  isoDateDaysAgo,
} from "../../api/signals";
import AccuracyTrendChart from "./AccuracyTrendChart";
import AccuracyDistributionChart from "./AccuracyDistributionChart";
import DailyViewAccuracyCard from "./DailyViewAccuracyCard";
import ConvictionCalibrationChart from "./ConvictionCalibrationChart";
import DailyAccuracyTrendChart from "./DailyAccuracyTrendChart";
import SectorAccuracyTable, { RegimeAccuracyTable } from "./SectorAccuracyTable";
import Card from "../common/Card";
import LoadingSkeleton from "../common/LoadingSkeleton";
import ErrorRetry from "../common/ErrorRetry";

const WINDOW_DAYS = 1;
const LOOKBACK_DAYS = 90;

export default function AccuracyTab() {
  const [legacyOpen, setLegacyOpen] = useState(false);
  const dateFrom = isoDateDaysAgo(LOOKBACK_DAYS);
  const params = { window_days: WINDOW_DAYS, date_from: dateFrom };

  const summaryQuery = useQuery({
    queryKey: ["daily-view-accuracy", params],
    queryFn: () => getDailyViewAccuracy(params),
  });
  const calibrationQuery = useQuery({
    queryKey: ["daily-view-calibration", params],
    queryFn: () => getDailyViewCalibration(params),
  });
  const trendQuery = useQuery({
    queryKey: ["daily-view-accuracy-trend", params],
    queryFn: () => getDailyViewAccuracyTrend(params),
  });
  const sectorQuery = useQuery({
    queryKey: ["daily-view-accuracy-sectors", params],
    queryFn: () => getDailyViewSectorAccuracy(params),
  });
  const regimeQuery = useQuery({
    queryKey: ["daily-view-accuracy-regimes", params],
    queryFn: () => getDailyViewRegimeAccuracy(params),
  });

  const { data: accuracyData } = useQuery({
    queryKey: ["signal-accuracy-summary"],
    queryFn: () => getSignalAccuracy({ window_days: 5 }),
    enabled: legacyOpen,
  });
  const { data: mlAccuracyData } = useQuery({
    queryKey: ["ml-accuracy-summary"],
    queryFn: () => getMLAccuracy({ window_days: 5 }),
    enabled: legacyOpen,
  });

  const loading =
    summaryQuery.isLoading ||
    calibrationQuery.isLoading ||
    trendQuery.isLoading ||
    sectorQuery.isLoading ||
    regimeQuery.isLoading;
  const error =
    summaryQuery.isError ||
    calibrationQuery.isError ||
    trendQuery.isError ||
    sectorQuery.isError ||
    regimeQuery.isError;

  return (
    <div className="space-y-8">
      {loading ? (
        <LoadingSkeleton variant="card" count={3} />
      ) : error ? (
        <ErrorRetry
          message="Failed to load daily-view accuracy"
          onRetry={() => {
            summaryQuery.refetch();
            calibrationQuery.refetch();
            trendQuery.refetch();
            sectorQuery.refetch();
            regimeQuery.refetch();
          }}
        />
      ) : (
        <>
          <Card padding="md">
            {summaryQuery.data && (
              <DailyViewAccuracyCard summary={summaryQuery.data} />
            )}
          </Card>

          <Card padding="md">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Conviction Calibration
            </h2>
            <ConvictionCalibrationChart buckets={calibrationQuery.data?.buckets ?? []} />
          </Card>

          <Card padding="md">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Accuracy Trend
            </h2>
            <DailyAccuracyTrendChart buckets={trendQuery.data?.buckets ?? []} />
          </Card>

          <Card padding="md">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">By Sector</h2>
            <SectorAccuracyTable sectors={sectorQuery.data?.sectors ?? []} />
          </Card>

          <Card padding="md">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">By Regime</h2>
            <RegimeAccuracyTable regimes={regimeQuery.data?.regimes ?? []} />
          </Card>
        </>
      )}

      <details
        className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
        onToggle={(e) => setLegacyOpen((e.target as HTMLDetailsElement).open)}
      >
        <summary className="cursor-pointer px-6 py-4 text-sm font-medium text-gray-700 dark:text-gray-300">
          Legacy Per-Signal Accuracy
        </summary>
        <div className="px-6 pb-6 space-y-8 border-t border-gray-200 dark:border-gray-700 pt-6">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Per-signal outcomes on absolute returns. Kept for debugging individual signals; the
            learning loop uses daily-view excess-return accuracy above.
          </p>

          {accuracyData && accuracyData.length > 0 && (() => {
            const summary = accuracyData[0]!;
            return (
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                  Overall Accuracy (5-Day Window)
                </h3>
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
              </div>
            );
          })()}

          {accuracyData && accuracyData.length > 0 && mlAccuracyData && mlAccuracyData.length > 0 && (() => {
            const rule = accuracyData[0]!;
            const ml = mlAccuracyData[0]!;
            return (
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                  ML vs Rule-Based (A/B Comparison)
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {rule.accuracy_pct.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Rule-Based</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                      {ml.accuracy_pct.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">ML Ensemble</p>
                  </div>
                  <div className="text-center">
                    <p className={`text-2xl font-bold ${ml.accuracy_pct > rule.accuracy_pct ? "text-emerald-600 dark:text-emerald-400" : ml.accuracy_pct < rule.accuracy_pct ? "text-red-600 dark:text-red-400" : "text-gray-500"}`}>
                      {ml.accuracy_pct > rule.accuracy_pct ? "+" : ""}{(ml.accuracy_pct - rule.accuracy_pct).toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">ML Delta</p>
                  </div>
                </div>
              </div>
            );
          })()}

          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
              Per-Signal Accuracy Trend
            </h3>
            <AccuracyTrendChart />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
              Per-Signal Accuracy Distribution
            </h3>
            <AccuracyDistributionChart />
          </div>
        </div>
      </details>
    </div>
  );
}
