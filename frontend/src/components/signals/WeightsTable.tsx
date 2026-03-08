import { useQuery } from "@tanstack/react-query";
import type { SignalWeights } from "../../types";
import { getSignalWeights } from "../../api/signals";
import LoadingSkeleton from "../common/LoadingSkeleton";
import ErrorRetry from "../common/ErrorRetry";

const WEIGHT_COLUMNS = [
  { key: "sentiment_momentum", label: "Sentiment" },
  { key: "sentiment_volume", label: "Sent. Vol" },
  { key: "price_momentum", label: "Price" },
  { key: "volume_anomaly", label: "Volume" },
  { key: "rsi", label: "RSI" },
  { key: "trend", label: "Trend" },
] as const;

const DEFAULT_WEIGHTS: Record<string, number> = {
  sentiment_momentum: 0.30,
  sentiment_volume: 0.20,
  price_momentum: 0.15,
  volume_anomaly: 0.10,
  rsi: 0.15,
  trend: 0.10,
};

function formatPct(val: number): string {
  return `${(val * 100).toFixed(0)}%`;
}

function deviationClass(val: number, key: string): string {
  const diff = Math.abs(val - (DEFAULT_WEIGHTS[key] ?? 0));
  if (diff > 0.05) return "text-amber-600 dark:text-amber-400 font-semibold";
  return "";
}

function accuracyColor(pct: number | null): string {
  if (pct == null) return "text-gray-400";
  if (pct > 55) return "text-emerald-600 dark:text-emerald-400";
  if (pct >= 50) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

export default function WeightsTable() {
  const { data: weights, isLoading, error, refetch } = useQuery<SignalWeights[]>({
    queryKey: ["signal-weights"],
    queryFn: getSignalWeights,
  });

  if (isLoading) return <LoadingSkeleton variant="row" count={5} />;
  if (error) return <ErrorRetry message="Failed to load signal weights" onRetry={refetch} />;
  if (!weights || weights.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        No adaptive weights computed yet. Weights are calculated after the feedback loop has enough samples.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            <th className="text-left py-2 px-3 font-medium text-gray-600 dark:text-gray-400">Sector</th>
            {WEIGHT_COLUMNS.map(({ label }) => (
              <th key={label} className="text-center py-2 px-2 font-medium text-gray-600 dark:text-gray-400">{label}</th>
            ))}
            <th className="text-center py-2 px-2 font-medium text-gray-600 dark:text-gray-400">Accuracy</th>
            <th className="text-center py-2 px-2 font-medium text-gray-600 dark:text-gray-400">Samples</th>
          </tr>
        </thead>
        <tbody>
          {weights.map((w, i) => (
            <tr
              key={i}
              className={`border-b border-gray-100 dark:border-gray-800 ${w.source === "global" ? "bg-blue-50/50 dark:bg-blue-900/10" : ""}`}
            >
              <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">
                {w.sector_name ?? "Global"}
                {w.source === "global" && (
                  <span className="ml-2 text-xs text-blue-600 dark:text-blue-400">(fallback)</span>
                )}
              </td>
              {WEIGHT_COLUMNS.map(({ key }) => (
                <td key={key} className={`text-center py-2 px-2 ${deviationClass(w[key], key)}`}>
                  {formatPct(w[key])}
                </td>
              ))}
              <td className={`text-center py-2 px-2 font-medium ${accuracyColor(w.accuracy_pct)}`}>
                {w.accuracy_pct != null ? `${w.accuracy_pct.toFixed(1)}%` : "—"}
              </td>
              <td className="text-center py-2 px-2 text-gray-600 dark:text-gray-400">
                {w.sample_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
