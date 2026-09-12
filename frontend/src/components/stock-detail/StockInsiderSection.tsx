import { useQuery } from "@tanstack/react-query";
import { getInsiderActivity } from "../../api/marketData";
import Card from "../common/Card";

interface StockInsiderSectionProps {
  ticker: string;
}

function scorePill(score: number | null) {
  if (score == null) {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
        No 30-day score
      </span>
    );
  }
  const bullish = score > 0.05;
  const bearish = score < -0.05;
  const styles = bullish
    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400"
    : bearish
      ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
      : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300";
  const label = bullish ? "Net buying" : bearish ? "Net selling" : "Neutral";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles}`}>
      {label} {score > 0 ? "+" : ""}
      {score.toFixed(3)}
    </span>
  );
}

function formatShares(shares: number | null): string {
  if (shares == null) return "—";
  return shares.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatValue(value: number | null): string {
  if (value == null) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function typeLabel(tx: string): string {
  return { P: "Buy", S: "Sell", A: "Award", D: "Dispose" }[tx] ?? tx;
}

export default function StockInsiderSection({ ticker }: StockInsiderSectionProps) {
  const { data } = useQuery({
    queryKey: ["insider-activity", ticker],
    queryFn: () => getInsiderActivity(ticker),
  });

  if (!data) return null;

  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Insider Activity
        </h2>
        {scorePill(data.insider_score)}
      </div>

      {data.transactions.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No insider transactions in the last 90 days
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
                <th className="text-left py-2 pr-3 font-medium">Date</th>
                <th className="text-left py-2 pr-3 font-medium">Insider</th>
                <th className="text-left py-2 pr-3 font-medium">Title</th>
                <th className="text-left py-2 pr-3 font-medium">Type</th>
                <th className="text-right py-2 pr-3 font-medium">Shares</th>
                <th className="text-right py-2 font-medium">Value</th>
              </tr>
            </thead>
            <tbody>
              {data.transactions.map((tx, i) => {
                const isBuy = tx.transaction_type === "P";
                const isSell = tx.transaction_type === "S";
                const typeClass = isBuy
                  ? "text-emerald-600 dark:text-emerald-400"
                  : isSell
                    ? "text-red-500/80 dark:text-red-400/80"
                    : "text-gray-600 dark:text-gray-400";
                return (
                  <tr key={`${tx.transaction_date}-${tx.insider_name}-${i}`} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 pr-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      {tx.transaction_date}
                    </td>
                    <td className="py-2 pr-3 text-gray-900 dark:text-white">
                      {tx.insider_name || "—"}
                    </td>
                    <td className="py-2 pr-3 text-gray-500 dark:text-gray-400">
                      {tx.insider_title || "—"}
                    </td>
                    <td className={`py-2 pr-3 font-medium ${typeClass}`}>
                      {typeLabel(tx.transaction_type)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-gray-700 dark:text-gray-300">
                      {formatShares(tx.shares)}
                    </td>
                    <td className={`py-2 text-right font-mono ${typeClass}`}>
                      {formatValue(tx.transaction_value)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
