import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createBacktest,
  listBacktests,
  getBacktest,
  deleteBacktest,
} from "../api/backtests";
import type { BacktestConfig } from "../types";
import BacktestForm from "../components/forms/BacktestForm";
import BacktestResultCard from "../components/backtests/BacktestResultCard";
import MetricsSummary from "../components/backtests/MetricsSummary";
import TradeLog from "../components/backtests/TradeLog";
import EquityCurveChart from "../components/charts/EquityCurveChart";
import LoadingSkeleton from "../components/common/LoadingSkeleton";

export default function BacktestPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(true);
  const queryClient = useQueryClient();

  // List backtests
  const { data: backtestsData, isLoading: listLoading } = useQuery({
    queryKey: ["backtests"],
    queryFn: () => listBacktests({ per_page: 50 }),
    refetchInterval: (query) => {
      // Poll while any backtest is pending/running
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
    enabled: selectedId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "pending" || data.status === "running")) {
        return 3000;
      }
      return false;
    },
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Backtesting
        </h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          {showForm ? "Hide Form" : "New Backtest"}
        </button>
      </div>

      {/* Configuration form */}
      {showForm && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
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
        </div>
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
                onSelect={setSelectedId}
                onDelete={(id) => deleteMutation.mutate(id)}
                isSelected={selectedId === bt.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail view */}
      {selectedId !== null && (
        <div className="space-y-4">
          {detailLoading ? (
            <LoadingSkeleton variant="chart" />
          ) : detail ? (
            <>
              {detail.status === "pending" || detail.status === "running" ? (
                <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6 text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Backtest is {detail.status}...
                  </p>
                </div>
              ) : detail.status === "failed" ? (
                <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
                  <p className="text-red-600 dark:text-red-400 font-medium">
                    Backtest failed
                  </p>
                  {detail.error_message && (
                    <p className="text-sm text-red-500 dark:text-red-400 mt-2">
                      {detail.error_message}
                    </p>
                  )}
                </div>
              ) : (
                <>
                  {/* Metrics */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                      Performance Metrics
                    </h2>
                    <MetricsSummary backtest={detail} />
                  </div>

                  {/* Equity curve */}
                  {detail.equity_curve.length > 0 && (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
                      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                        Equity Curve
                      </h2>
                      <EquityCurveChart
                        data={detail.equity_curve}
                        startingCapital={detail.starting_capital}
                      />
                    </div>
                  )}

                  {/* Trade log */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                      Trade Log ({detail.trades.length} trades)
                    </h2>
                    <TradeLog trades={detail.trades} />
                  </div>
                </>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
