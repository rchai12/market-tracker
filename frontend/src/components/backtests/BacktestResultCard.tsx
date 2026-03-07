import type { BacktestSummary } from "../../types";
import { formatTimeAgo } from "../../utils/format";

interface BacktestResultCardProps {
  backtest: BacktestSummary;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  isSelected: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

export default function BacktestResultCard({
  backtest,
  onSelect,
  onDelete,
  isSelected,
}: BacktestResultCardProps) {
  const statusStyle = STATUS_STYLES[backtest.status] || STATUS_STYLES.pending;
  const label = backtest.ticker || backtest.sector_name || "Unknown";
  const isComplete = backtest.status === "completed";

  return (
    <div
      onClick={() => onSelect(backtest.id)}
      className={`bg-white dark:bg-gray-800 rounded-lg shadow p-4 cursor-pointer transition-all hover:ring-2 hover:ring-blue-400 dark:hover:ring-blue-500 ${
        isSelected ? "ring-2 ring-blue-500 dark:ring-blue-400" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-lg font-semibold text-gray-900 dark:text-white">
          {label}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyle}`}
        >
          {backtest.status}
        </span>
      </div>

      <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mb-3">
        <span className="capitalize">{backtest.mode}</span>
        <span>&middot;</span>
        <span>{backtest.min_signal_strength}+</span>
        <span>&middot;</span>
        <span>${Number(backtest.starting_capital).toLocaleString()}</span>
      </div>

      {isComplete && backtest.total_return_pct !== null && (
        <div className="grid grid-cols-3 gap-2 text-sm mb-3">
          <div className="text-center">
            <p
              className={`font-semibold ${
                backtest.total_return_pct >= 0
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {backtest.total_return_pct >= 0 ? "+" : ""}
              {backtest.total_return_pct.toFixed(2)}%
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Return</p>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900 dark:text-white">
              {backtest.sharpe_ratio !== null
                ? backtest.sharpe_ratio.toFixed(2)
                : "N/A"}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Sharpe</p>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900 dark:text-white">
              {backtest.total_trades ?? 0}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Trades</p>
          </div>
        </div>
      )}

      {backtest.status === "failed" && backtest.error_message && (
        <p className="text-xs text-red-500 dark:text-red-400 line-clamp-2 mb-2">
          {backtest.error_message}
        </p>
      )}

      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {formatTimeAgo(backtest.created_at)}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(backtest.id);
          }}
          className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
