import { useQuery } from "@tanstack/react-query";
import { getEarningsHistory } from "../../api/marketData";
import type { EarningsEstimateResponse } from "../../types/earnings";
import Card from "../common/Card";

interface StockEarningsSectionProps {
  ticker: string;
}

function isActiveWindow(dateStr: string): boolean {
  const reported = new Date(`${dateStr}T00:00:00`);
  const now = new Date();
  const diffDays = (now.getTime() - reported.getTime()) / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= 2;
}

function formatEps(val: number | null): string {
  if (val == null) return "—";
  return val.toFixed(2);
}

function formatSurprise(val: number | null): string {
  if (val == null) return "—";
  const sign = val > 0 ? "+" : "";
  return `${sign}${val.toFixed(1)}%`;
}

function surpriseClass(val: number | null): string {
  if (val == null || val === 0) return "text-gray-900 dark:text-white";
  return val > 0
    ? "text-emerald-600 dark:text-emerald-400"
    : "text-red-600 dark:text-red-400";
}

export default function StockEarningsSection({ ticker }: StockEarningsSectionProps) {
  const { data: earnings } = useQuery<EarningsEstimateResponse[]>({
    queryKey: ["earnings-history", ticker],
    queryFn: () => getEarningsHistory(ticker, 8),
  });

  if (!earnings || earnings.length === 0) return null;

  return (
    <Card className="mt-4">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
        Earnings History
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <th className="py-2 pr-3 font-medium">Date</th>
              <th className="py-2 px-3 font-medium text-right">Est. EPS</th>
              <th className="py-2 px-3 font-medium text-right">Actual EPS</th>
              <th className="py-2 px-3 font-medium text-right">Surprise</th>
              <th className="py-2 pl-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {earnings.map((row) => {
              const active = row.reported && isActiveWindow(row.earnings_date);
              return (
                <tr
                  key={row.id}
                  className={`border-b border-gray-100 dark:border-gray-800 last:border-0 ${
                    active ? "bg-amber-50 dark:bg-amber-900/20" : ""
                  }`}
                >
                  <td className="py-2 pr-3 text-gray-900 dark:text-white whitespace-nowrap">
                    {row.earnings_date}
                    {active && (
                      <span className="ml-2 text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400">
                        scoring
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-gray-700 dark:text-gray-300">
                    {formatEps(row.estimated_eps)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-gray-700 dark:text-gray-300">
                    {formatEps(row.actual_eps)}
                  </td>
                  <td className={`py-2 px-3 text-right font-mono font-medium ${surpriseClass(row.surprise_pct)}`}>
                    {formatSurprise(row.surprise_pct)}
                  </td>
                  <td className="py-2 pl-3 text-gray-600 dark:text-gray-400">
                    {row.reported ? "Reported" : "Upcoming"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
