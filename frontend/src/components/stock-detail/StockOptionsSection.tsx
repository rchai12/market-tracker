import { useQuery } from "@tanstack/react-query";
import { getOptionsActivity } from "../../api/marketData";
import Card from "../common/Card";

interface StockOptionsSectionProps {
  ticker: string;
}

function qualityBadge(quality: string) {
  const styles: Record<string, string> = {
    full: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
    partial: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    stale: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[quality] ?? styles.stale}`}>
      {quality}
    </span>
  );
}

function formatVol(vol: number | null): string {
  if (vol == null) return "—";
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`;
  return vol.toString();
}

function formatPct(val: number | null): string {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

export default function StockOptionsSection({ ticker }: StockOptionsSectionProps) {
  const { data: optionsData } = useQuery({
    queryKey: ["options-activity", ticker],
    queryFn: () => getOptionsActivity(ticker, { days: 30 }),
  });

  if (!optionsData || optionsData.length === 0) return null;

  const latest = optionsData[optionsData.length - 1]!;

  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Options Flow
        </h2>
        {qualityBadge(latest.data_quality)}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        {/* Put/Call Ratio */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">P/C Ratio</p>
          <p className={`text-xl font-bold ${
            latest.put_call_ratio != null && latest.put_call_ratio > 1
              ? "text-red-600 dark:text-red-400"
              : "text-emerald-600 dark:text-emerald-400"
          }`}>
            {latest.put_call_ratio?.toFixed(2) ?? "—"}
          </p>
        </div>

        {/* IV */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Avg IV</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">
            {formatPct(latest.weighted_avg_iv)}
          </p>
        </div>

        {/* IV Skew */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">IV Skew</p>
          <p className={`text-xl font-bold ${
            latest.iv_skew != null && latest.iv_skew > 0
              ? "text-red-600 dark:text-red-400"
              : "text-emerald-600 dark:text-emerald-400"
          }`}>
            {latest.iv_skew != null ? `${latest.iv_skew > 0 ? "+" : ""}${(latest.iv_skew * 100).toFixed(1)}%` : "—"}
          </p>
        </div>

        {/* Expirations */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Expirations</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">
            {latest.expirations_fetched}
          </p>
        </div>
      </div>

      {/* Volume Summary */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Call Volume</span>
            <span className="font-medium text-emerald-600 dark:text-emerald-400">{formatVol(latest.total_call_volume)}</span>
          </div>
          <div className="flex justify-between text-sm mt-1">
            <span className="text-gray-500 dark:text-gray-400">Call OI</span>
            <span className="font-medium text-gray-900 dark:text-white">{formatVol(latest.total_call_oi)}</span>
          </div>
        </div>
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Put Volume</span>
            <span className="font-medium text-red-600 dark:text-red-400">{formatVol(latest.total_put_volume)}</span>
          </div>
          <div className="flex justify-between text-sm mt-1">
            <span className="text-gray-500 dark:text-gray-400">Put OI</span>
            <span className="font-medium text-gray-900 dark:text-white">{formatVol(latest.total_put_oi)}</span>
          </div>
        </div>
      </div>

      {/* P/C Ratio History */}
      {optionsData.length > 1 && (
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            P/C Ratio History ({optionsData.length} days)
          </p>
          <div className="flex items-end gap-0.5 h-16">
            {optionsData.map((d, i) => {
              const pcr = d.put_call_ratio;
              if (pcr == null) return <div key={i} className="flex-1" />;
              const maxPcr = Math.max(...optionsData.map(x => x.put_call_ratio ?? 0), 2);
              const height = Math.min(pcr / maxPcr, 1) * 100;
              return (
                <div
                  key={i}
                  className={`flex-1 rounded-t ${pcr > 1 ? "bg-red-400 dark:bg-red-500" : "bg-emerald-400 dark:bg-emerald-500"}`}
                  style={{ height: `${height}%` }}
                  title={`${d.date}: ${pcr.toFixed(2)}`}
                />
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{optionsData[0]?.date}</span>
            <span className="border-t border-dashed border-gray-400 flex-1 mx-2 mt-1.5" />
            <span>{latest.date}</span>
          </div>
        </div>
      )}
    </Card>
  );
}
