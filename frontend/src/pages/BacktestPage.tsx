import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createBacktest,
  listBacktests,
  getBacktest,
  deleteBacktest,
  exportBacktest,
} from "../api/backtests";
import type { BacktestConfig } from "../types";
import BacktestForm from "../components/forms/BacktestForm";
import BacktestResultCard from "../components/backtests/BacktestResultCard";
import MetricsSummary from "../components/backtests/MetricsSummary";
import TradeLog from "../components/backtests/TradeLog";
import EquityCurveChart from "../components/charts/EquityCurveChart";
import BacktestCompare from "../components/backtests/BacktestCompare";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import Card from "../components/common/Card";

export default function BacktestPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(true);
  const [compareMode, setCompareMode] = useState(false);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const queryClient = useQueryClient();

  // List backtests
  const { data: backtestsData, isLoading: listLoading } = useQuery({
    queryKey: ["backtests"],
    queryFn: () => listBacktests({ per_page: 50 }),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (
        data?.data.some(
          (bt) => bt.status === "pending" || bt.status === "running"
        )
      ) {
        return 3000;
      }
      return false;
    },
  });

  // Detail query
  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["backtest", selectedId],
    queryFn: () => getBacktest(selectedId!),
    enabled: selectedId !== null && !compareMode,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "pending" || data.status === "running")) {
        return 3000;
      }
      return false;
    },
  });

  // Compare queries
  const { data: compare1 } = useQuery({
    queryKey: ["backtest", compareIds[0]],
    queryFn: () => getBacktest(compareIds[0]!),
    enabled: compareIds.length === 2,
  });
  const { data: compare2 } = useQuery({
    queryKey: ["backtest", compareIds[1]],
    queryFn: () => getBacktest(compareIds[1]!),
    enabled: compareIds.length === 2,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (config: BacktestConfig) => createBacktest(config),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
      setSelectedId(data.id);
      setShowForm(false);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteBacktest(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
      if (selectedId === deletedId) {
        setSelectedId(null);
      }
    },
  });

  const backtests = backtestsData?.data ?? [];

  const handleCardClick = (id: number) => {
    if (compareMode) {
      setCompareIds((prev) => {
        if (prev.includes(id)) return prev.filter((x) => x !== id);
        if (prev.length < 2) return [...prev, id];
        return [prev[1]!, id];
      });
    } else {
      setSelectedId(id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Backtesting
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setCompareMode(!compareMode);
              setCompareIds([]);
            }}
            className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
              compareMode
                ? "bg-indigo-50 border-indigo-500 text-indigo-700 dark:bg-indigo-900/30 dark:border-indigo-500 dark:text-indigo-400"
                : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            }`}
          >
            Compare
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            {showForm ? "Hide Form" : "New Backtest"}
          </button>
        </div>
      </div>

      {/* Compare mode banner */}
      {compareMode && (
        <div className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg p-3 flex items-center justify-between">
          <span className="text-sm text-indigo-700 dark:text-indigo-300">
            {compareIds.length === 0
              ? "Select two completed backtests to compare"
              : compareIds.length === 1
                ? "Select one more backtest"
                : "Comparing two backtests"}
          </span>
          <button
            onClick={() => {
              setCompareMode(false);
              setCompareIds([]);
            }}
            className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-800"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Configuration form */}
      {showForm && !compareMode && (
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Configure Backtest
          </h2>
          <BacktestForm
            onSubmit={(config) => createMutation.mutate(config)}
            isSubmitting={createMutation.isPending}
          />
          {createMutation.isError && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">
              Failed to create backtest. Check your inputs and try again.
            </p>
          )}
        </Card>
      )}

      {/* Past backtests list */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Backtests
        </h2>
        {listLoading ? (
          <LoadingSkeleton variant="card" count={3} />
        ) : backtests.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
            No backtests yet. Configure and run one above.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {backtests.map((bt) => (
              <BacktestResultCard
                key={bt.id}
                backtest={bt}
                onSelect={handleCardClick}
                onDelete={(id) => deleteMutation.mutate(id)}
                isSelected={
                  compareMode
                    ? compareIds.includes(bt.id)
                    : selectedId === bt.id
                }
              />
            ))}
          </div>
        )}
      </div>

      {/* Compare view */}
      {compareMode && compareIds.length === 2 && compare1 && compare2 && (
        <BacktestCompare
          backtest1={compare1}
          backtest2={compare2}
          onClose={() => {
            setCompareMode(false);
            setCompareIds([]);
          }}
        />
      )}

      {/* Detail view */}
      {!compareMode && selectedId !== null && (
        <div className="space-y-4">
          {detailLoading ? (
            <LoadingSkeleton variant="chart" />
          ) : detail ? (
            <>
              {detail.status === "pending" || detail.status === "running" ? (
                <Card padding="md" className="text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Backtest is {detail.status}...
                  </p>
                </Card>
              ) : detail.status === "failed" ? (
                <Card padding="md">
                  <p className="text-red-600 dark:text-red-400 font-medium">
                    Backtest failed
                  </p>
                  {detail.error_message && (
                    <p className="text-sm text-red-500 dark:text-red-400 mt-2">
                      {detail.error_message}
                    </p>
                  )}
                </Card>
              ) : (
                <>
                  {/* Metrics */}
                  <Card padding="md">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                      Performance Metrics
                    </h2>
                    <MetricsSummary backtest={detail} />
                  </Card>

                  {/* Equity curve */}
                  {detail.equity_curve.length > 0 && (
                    <Card padding="md">
                      <div className="flex items-center justify-between mb-3">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                          Equity Curve
                        </h2>
                        <button
                          onClick={() => exportBacktest(selectedId!, "equity_curve")}
                          className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          Export CSV
                        </button>
                      </div>
                      <EquityCurveChart
                        data={detail.equity_curve}
                        startingCapital={detail.starting_capital}
                        benchmarkData={detail.benchmark_equity_curve}
                        benchmarkLabel={detail.benchmark_ticker || "SPY"}
                      />
                    </Card>
                  )}

                  {/* Trade log */}
                  <Card padding="md">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Trade Log ({detail.trades.length} trades)
                      </h2>
                      <button
                        onClick={() => exportBacktest(selectedId!, "trades")}
                        className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                      >
                        Export CSV
                      </button>
                    </div>
                    <TradeLog trades={detail.trades} />
                  </Card>
                </>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
