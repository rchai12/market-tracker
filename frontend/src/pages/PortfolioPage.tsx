import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getPortfolioPerformance,
  getPortfolioPositions,
  getPortfolioStats,
  getPortfolioSummary,
  getPortfolioTrades,
} from "../api/portfolio";
import EquityCurveChart from "../components/charts/EquityCurveChart";
import Card from "../components/common/Card";
import ErrorRetry from "../components/common/ErrorRetry";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import type { PortfolioPosition, PortfolioTrade } from "../types/portfolio";

const EXIT_REASON_STYLES: Record<string, string> = {
  signal_reversal: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  stop_loss: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  take_profit: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  max_positions: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400",
};

const EXIT_REASON_LABELS: Record<string, string> = {
  signal_reversal: "Reversal",
  stop_loss: "Stop Loss",
  take_profit: "Take Profit",
  max_positions: "Max Positions",
};

function formatPct(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

function pnlClass(value: number | null | undefined): string {
  if (value == null) return "text-gray-500 dark:text-gray-400";
  if (value > 0) return "text-green-600 dark:text-green-400";
  if (value < 0) return "text-red-600 dark:text-red-400";
  return "text-gray-500 dark:text-gray-400";
}

function isNotFoundError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  return (error as { response?: { status?: number } }).response?.status === 404;
}

export default function PortfolioPage() {
  const [tradePage, setTradePage] = useState(1);

  const summaryQuery = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: getPortfolioSummary,
    retry: false,
  });
  const positionsQuery = useQuery({
    queryKey: ["portfolio-positions"],
    queryFn: getPortfolioPositions,
    enabled: summaryQuery.isSuccess,
  });
  const performanceQuery = useQuery({
    queryKey: ["portfolio-performance"],
    queryFn: getPortfolioPerformance,
    enabled: summaryQuery.isSuccess,
  });
  const statsQuery = useQuery({
    queryKey: ["portfolio-stats"],
    queryFn: getPortfolioStats,
    enabled: summaryQuery.isSuccess,
  });
  const tradesQuery = useQuery({
    queryKey: ["portfolio-trades", tradePage],
    queryFn: () => getPortfolioTrades(tradePage, 20),
    enabled: summaryQuery.isSuccess,
  });

  if (summaryQuery.isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Portfolio</h1>
        <LoadingSkeleton variant="card" count={3} />
      </div>
    );
  }

  if (summaryQuery.isError || !summaryQuery.data) {
    const empty = isNotFoundError(summaryQuery.error);
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Portfolio</h1>
        <Card padding="md">
          {empty ? (
            <p className="text-sm text-gray-600 dark:text-gray-400">
              No paper portfolio yet. Enable <code className="font-mono">PAPER_PORTFOLIO_ENABLED</code>{" "}
              and wait for the :35 weekday task to create it.
            </p>
          ) : (
            <ErrorRetry message="Could not load portfolio" onRetry={() => summaryQuery.refetch()} />
          )}
        </Card>
      </div>
    );
  }

  const summary = summaryQuery.data;
  const vsSpy =
    summary.benchmark_return_pct == null
      ? ""
      : ` vs ${summary.benchmark_ticker} ${formatPct(summary.benchmark_return_pct)}`;

  const starting = summary.starting_capital || 1;
  const equityData =
    performanceQuery.data?.points.map((p) => ({
      date: p.date,
      equity: (p.total_value / starting) * 100,
    })) ?? [];
  const benchmarkData =
    performanceQuery.data?.points
      .filter((p) => p.benchmark_value != null)
      .map((p) => ({
        date: p.date,
        equity: ((p.benchmark_value as number) / starting) * 100,
      })) ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Paper Portfolio</h1>

      <Card padding="md">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Portfolio Value</p>
            <p className="text-3xl font-semibold text-gray-900 dark:text-white">
              ${summary.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
            <p className={`mt-1 text-sm font-medium ${pnlClass(summary.total_return_pct)}`}>
              {formatPct(summary.total_return_pct)}
              {vsSpy}
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-gray-500 dark:text-gray-400">Inception</p>
              <p className="font-medium text-gray-900 dark:text-white">{summary.inception_date}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Cash</p>
              <p className="font-medium text-gray-900 dark:text-white">{summary.cash_pct.toFixed(0)}%</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Positions</p>
              <p className="font-medium text-gray-900 dark:text-white">{summary.open_positions}</p>
            </div>
          </div>
        </div>
      </Card>

      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Equity Curve</h2>
        {equityData.length > 1 ? (
          <EquityCurveChart
            data={equityData}
            startingCapital={100}
            benchmarkData={benchmarkData.length > 1 ? benchmarkData : null}
            benchmarkLabel={summary.benchmark_ticker}
          />
        ) : (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Equity curve appears after the first daily snapshot (21:30 UTC).
          </p>
        )}
      </Card>

      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Open Positions</h2>
        <PositionsTable positions={positionsQuery.data ?? []} />
      </Card>

      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Performance Stats</h2>
        {statsQuery.data ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <Stat label="Sharpe" value={statsQuery.data.sharpe_ratio?.toFixed(2) ?? "—"} />
            <Stat
              label="Max DD"
              value={
                statsQuery.data.max_drawdown_pct == null
                  ? "—"
                  : `-${statsQuery.data.max_drawdown_pct.toFixed(1)}%`
              }
            />
            <Stat label="Win Rate" value={formatPct(statsQuery.data.win_rate_pct, 0)} />
            <Stat label="Jensen Alpha" value={formatPct(statsQuery.data.alpha)} />
            <Stat label="Beta" value={statsQuery.data.beta?.toFixed(2) ?? "—"} />
            <Stat label="Avg Win" value={formatPct(statsQuery.data.avg_win_pct)} />
            <Stat label="Avg Loss" value={formatPct(statsQuery.data.avg_loss_pct)} />
          </div>
        ) : (
          <p className="text-sm text-gray-500 dark:text-gray-400">Not enough snapshot history yet.</p>
        )}
      </Card>

      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Trade History</h2>
        <TradesTable trades={tradesQuery.data?.data ?? []} />
        {tradesQuery.data && tradesQuery.data.meta.total_pages > 1 && (
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              disabled={tradePage <= 1}
              onClick={() => setTradePage((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={tradePage >= tradesQuery.data.meta.total_pages}
              onClick={() => setTradePage((p) => p + 1)}
              className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-gray-500 dark:text-gray-400">{label}</p>
      <p className="font-medium text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}

function PositionsTable({ positions }: { positions: PortfolioPosition[] }) {
  if (positions.length === 0) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">No open positions.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="pb-2 pr-4">Ticker</th>
            <th className="pb-2 pr-4">Sector</th>
            <th className="pb-2 pr-4">Entry</th>
            <th className="pb-2 pr-4 text-right">Current</th>
            <th className="pb-2 text-right">P&L</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
          {positions.map((pos) => (
            <tr key={pos.id} className="text-gray-900 dark:text-gray-200">
              <td className="py-2 pr-4 font-medium">
                <Link to={`/stocks/${pos.ticker}`} className="hover:underline">
                  {pos.ticker}
                </Link>
              </td>
              <td className="py-2 pr-4 text-gray-500 dark:text-gray-400">{pos.sector ?? "—"}</td>
              <td className="py-2 pr-4">${pos.entry_price.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right">
                {pos.current_price == null ? "—" : `$${pos.current_price.toFixed(2)}`}
              </td>
              <td className={`py-2 text-right font-medium ${pnlClass(pos.unrealized_pnl_pct)}`}>
                {formatPct(pos.unrealized_pnl_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradesTable({ trades }: { trades: PortfolioTrade[] }) {
  if (trades.length === 0) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">No closed trades yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="pb-2 pr-4">Closed</th>
            <th className="pb-2 pr-4">Ticker</th>
            <th className="pb-2 pr-4 text-right">Entry → Exit</th>
            <th className="pb-2 pr-4 text-right">Return</th>
            <th className="pb-2">Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
          {trades.map((trade) => (
            <tr key={trade.id} className="text-gray-900 dark:text-gray-200">
              <td className="py-2 pr-4 whitespace-nowrap">
                {new Date(trade.closed_at).toLocaleDateString()}
              </td>
              <td className="py-2 pr-4 font-medium">{trade.ticker}</td>
              <td className="py-2 pr-4 text-right">
                ${trade.entry_price.toFixed(2)} → ${trade.exit_price.toFixed(2)}
              </td>
              <td className={`py-2 pr-4 text-right font-medium ${pnlClass(trade.return_pct)}`}>
                {formatPct(trade.return_pct)}
              </td>
              <td className="py-2">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    EXIT_REASON_STYLES[trade.exit_reason] ?? EXIT_REASON_STYLES.max_positions
                  }`}
                >
                  {EXIT_REASON_LABELS[trade.exit_reason] ?? trade.exit_reason}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
