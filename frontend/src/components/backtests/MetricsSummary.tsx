import type { BacktestDetail } from "../../types";

interface MetricsSummaryProps {
  backtest: BacktestDetail;
}

interface MetricCardProps {
  label: string;
  value: string;
  colorClass?: string;
}

function MetricCard({ label, value, colorClass }: MetricCardProps) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
      <p className={`text-lg font-semibold ${colorClass || "text-gray-900 dark:text-white"}`}>
        {value}
      </p>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{label}</p>
    </div>
  );
}

function formatPct(val: number | null, showSign = false): string {
  if (val === null) return "N/A";
  const prefix = showSign && val > 0 ? "+" : "";
  return `${prefix}${val.toFixed(2)}%`;
}

function getReturnColor(val: number | null): string {
  if (val === null) return "text-gray-900 dark:text-white";
  return val >= 0
    ? "text-green-600 dark:text-green-400"
    : "text-red-600 dark:text-red-400";
}

export default function MetricsSummary({ backtest }: MetricsSummaryProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MetricCard
        label="Total Return"
        value={formatPct(backtest.total_return_pct, true)}
        colorClass={getReturnColor(backtest.total_return_pct)}
      />
      <MetricCard
        label="Annualized Return"
        value={formatPct(backtest.annualized_return_pct, true)}
        colorClass={getReturnColor(backtest.annualized_return_pct)}
      />
      <MetricCard
        label="Sharpe Ratio"
        value={backtest.sharpe_ratio !== null ? backtest.sharpe_ratio.toFixed(2) : "N/A"}
      />
      <MetricCard
        label="Max Drawdown"
        value={formatPct(backtest.max_drawdown_pct)}
        colorClass="text-red-600 dark:text-red-400"
      />
      <MetricCard
        label="Win Rate"
        value={formatPct(backtest.win_rate_pct)}
      />
      <MetricCard
        label="Total Trades"
        value={backtest.total_trades !== null ? String(backtest.total_trades) : "0"}
      />
      <MetricCard
        label="Best Trade"
        value={formatPct(backtest.best_trade_pct, true)}
        colorClass={getReturnColor(backtest.best_trade_pct)}
      />
      <MetricCard
        label="Worst Trade"
        value={formatPct(backtest.worst_trade_pct, true)}
        colorClass={getReturnColor(backtest.worst_trade_pct)}
      />
    </div>
  );
}
