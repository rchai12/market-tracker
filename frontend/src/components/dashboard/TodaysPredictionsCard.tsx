import { Link } from "react-router-dom";
import type { DailySignalView, TodaysPredictions } from "../../types";
import Card from "../common/Card";
import { ConvictionBar, DirectionChip } from "../signals/DailyViewBadge";

interface TodaysPredictionsCardProps {
  payload: TodaysPredictions;
}

function formatDate(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

function changeClass(view: DailySignalView): string {
  if (view.outcome_1d) {
    return view.outcome_1d.is_correct
      ? "text-green-600 dark:text-green-400"
      : "text-red-600 dark:text-red-400";
  }
  return "text-gray-700 dark:text-gray-300";
}

function changeValue(view: DailySignalView): number | null {
  if (view.outcome_1d) return view.outcome_1d.price_change_pct;
  return view.live_change_pct;
}

export default function TodaysPredictionsCard({ payload }: TodaysPredictionsCardProps) {
  const isLive = payload.data.some((row) => row.outcome_1d == null);

  return (
    <Card padding="none" className="overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Today's Predictions</h2>
        <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
          <span>{formatDate(payload.trading_date)}</span>
          {isLive && (
            <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              Live
            </span>
          )}
        </div>
      </div>
      {payload.data.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-8 px-4">
          No daily views yet. Predictions appear after the next signal generation run.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
                <th className="text-left px-4 py-2 font-medium">Ticker</th>
                <th className="text-left px-4 py-2 font-medium">Sector</th>
                <th className="text-left px-4 py-2 font-medium">Direction</th>
                <th className="text-left px-4 py-2 font-medium">Conviction</th>
                <th className="text-right px-4 py-2 font-medium">Signals</th>
                <th className="text-right px-4 py-2 font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {payload.data.map((row) => (
                <tr
                  key={`${row.ticker}-${row.trading_date}`}
                  className="border-b border-gray-100 dark:border-gray-700/50 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-700/30"
                >
                  <td className="px-4 py-2">
                    <Link
                      to={`/stocks/${row.ticker}`}
                      className="font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400"
                    >
                      {row.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-gray-500 dark:text-gray-400 truncate max-w-[10rem]">
                    {row.sector ?? "—"}
                  </td>
                  <td className="px-4 py-2">
                    <DirectionChip direction={row.direction} />
                  </td>
                  <td className="px-4 py-2">
                    <ConvictionBar value={row.conviction} />
                  </td>
                  <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">
                    {row.signal_count}
                  </td>
                  <td className={`px-4 py-2 text-right font-mono ${changeClass(row)}`}>
                    {formatPct(changeValue(row))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
