import type { BacktestDetail, EquityPoint } from "../../types";
import EquityCurveChart from "../charts/EquityCurveChart";

interface BacktestCompareProps {
  backtest1: BacktestDetail;
  backtest2: BacktestDetail;
  onClose: () => void;
}

function formatPct(val: number | null, showSign = false): string {
  if (val === null) return "N/A";
  const prefix = showSign && val > 0 ? "+" : "";
  return `${prefix}${val.toFixed(2)}%`;
}

function formatNum(val: number | null): string {
  if (val === null) return "N/A";
  return val.toFixed(2);
}

interface CompareRowProps {
  label: string;
  val1: string;
  val2: string;
  higherIsBetter?: boolean;
  num1?: number | null;
  num2?: number | null;
}

function CompareRow({ label, val1, val2, higherIsBetter = true, num1, num2 }: CompareRowProps) {
  let class1 = "text-gray-900 dark:text-white";
  let class2 = "text-gray-900 dark:text-white";

  if (num1 !== undefined && num2 !== undefined && num1 !== null && num2 !== null) {
    const better1 = higherIsBetter ? num1 > num2 : num1 < num2;
    const better2 = higherIsBetter ? num2 > num1 : num2 < num1;
    if (better1) class1 = "text-green-600 dark:text-green-400 font-semibold";
    if (better2) class2 = "text-green-600 dark:text-green-400 font-semibold";
  }

  return (
    <tr className="border-b border-gray-100 dark:border-gray-700/50">
      <td className="py-2 pr-4 text-sm text-gray-500 dark:text-gray-400">{label}</td>
      <td className={`py-2 pr-4 text-sm text-right ${class1}`}>{val1}</td>
      <td className={`py-2 text-sm text-right ${class2}`}>{val2}</td>
    </tr>
  );
}

function getLabel(bt: BacktestDetail): string {
  const target = bt.ticker || bt.sector_name || "Unknown";
  return `${target} (${bt.mode})`;
}

export default function BacktestCompare({ backtest1, backtest2, onClose }: BacktestCompareProps) {
  // Normalize equity curves to percentage (100% = starting capital) for fair comparison
  const normalize = (curve: EquityPoint[], capital: number): EquityPoint[] =>
    curve.map((p) => ({ date: p.date, equity: (p.equity / capital) * 100 }));

  const label1 = getLabel(backtest1);
  const label2 = getLabel(backtest2);

  // For the overlay chart, use normalized curves as separate data sets
  // We'll overlay by using the benchmark slot for the second backtest
  const normalizedData1 = normalize(backtest1.equity_curve, backtest1.starting_capital);
  const normalizedData2 = normalize(backtest2.equity_curve, backtest2.starting_capital);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Comparison
        </h2>
        <button
          onClick={onClose}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
        >
          Close
        </button>
      </div>

      {/* Overlaid equity curves (normalized to 100%) */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          Equity Curves (normalized to 100%)
        </h3>
        <EquityCurveChart
          data={normalizedData1}
          startingCapital={100}
          benchmarkData={normalizedData2}
          benchmarkLabel={label2}
          height={350}
        />
        <div className="flex gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-green-500 inline-block" /> {label1}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-indigo-500 inline-block" /> {label2}
          </span>
        </div>
      </div>

      {/* Metrics comparison table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          Metrics
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="pb-2 text-left text-xs text-gray-500 dark:text-gray-400">Metric</th>
                <th className="pb-2 text-right text-xs text-green-600 dark:text-green-400">{label1}</th>
                <th className="pb-2 text-right text-xs text-indigo-600 dark:text-indigo-400">{label2}</th>
              </tr>
            </thead>
            <tbody>
              <CompareRow
                label="Total Return"
                val1={formatPct(backtest1.total_return_pct, true)}
                val2={formatPct(backtest2.total_return_pct, true)}
                num1={backtest1.total_return_pct}
                num2={backtest2.total_return_pct}
              />
              <CompareRow
                label="Annualized Return"
                val1={formatPct(backtest1.annualized_return_pct, true)}
                val2={formatPct(backtest2.annualized_return_pct, true)}
                num1={backtest1.annualized_return_pct}
                num2={backtest2.annualized_return_pct}
              />
              <CompareRow
                label="Sharpe Ratio"
                val1={formatNum(backtest1.sharpe_ratio)}
                val2={formatNum(backtest2.sharpe_ratio)}
                num1={backtest1.sharpe_ratio}
                num2={backtest2.sharpe_ratio}
              />
              <CompareRow
                label="Max Drawdown"
                val1={formatPct(backtest1.max_drawdown_pct)}
                val2={formatPct(backtest2.max_drawdown_pct)}
                num1={backtest1.max_drawdown_pct}
                num2={backtest2.max_drawdown_pct}
                higherIsBetter={false}
              />
              <CompareRow
                label="Win Rate"
                val1={formatPct(backtest1.win_rate_pct)}
                val2={formatPct(backtest2.win_rate_pct)}
                num1={backtest1.win_rate_pct}
                num2={backtest2.win_rate_pct}
              />
              <CompareRow
                label="Total Trades"
                val1={String(backtest1.total_trades ?? 0)}
                val2={String(backtest2.total_trades ?? 0)}
              />
              <CompareRow
                label="Best Trade"
                val1={formatPct(backtest1.best_trade_pct, true)}
                val2={formatPct(backtest2.best_trade_pct, true)}
                num1={backtest1.best_trade_pct}
                num2={backtest2.best_trade_pct}
              />
              <CompareRow
                label="Worst Trade"
                val1={formatPct(backtest1.worst_trade_pct, true)}
                val2={formatPct(backtest2.worst_trade_pct, true)}
                num1={backtest1.worst_trade_pct}
                num2={backtest2.worst_trade_pct}
              />
              <CompareRow
                label="Final Equity"
                val1={backtest1.final_equity !== null ? `$${backtest1.final_equity.toLocaleString()}` : "N/A"}
                val2={backtest2.final_equity !== null ? `$${backtest2.final_equity.toLocaleString()}` : "N/A"}
                num1={backtest1.final_equity}
                num2={backtest2.final_equity}
              />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
