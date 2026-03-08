import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { listSignals, getSignalAccuracy } from "../api/signals";
import { listSectors } from "../api/stocks";
import type { Signal } from "../types";
import SignalCard from "../components/signals/SignalCard";
import SignalDetailPanel from "../components/signals/SignalDetailPanel";
import AccuracyTrendChart from "../components/signals/AccuracyTrendChart";
import AccuracyDistributionChart from "../components/signals/AccuracyDistributionChart";
import WeightsTable from "../components/signals/WeightsTable";
import LoadingSkeleton from "../components/common/LoadingSkeleton";

type Tab = "signals" | "accuracy" | "methodology";

export default function SignalsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [direction, setDirection] = useState<string>("");
  const [strength, setStrength] = useState<string>("");
  const [ticker, setTicker] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("signals");
  const [detailSignal, setDetailSignal] = useState<Signal | null>(null);

  const effectiveSector = searchParams.get("sector") || "";

  const { data: sectors } = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
    staleTime: 5 * 60 * 1000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["signals", page, direction, strength, ticker, effectiveSector],
    queryFn: () =>
      listSignals({
        page,
        per_page: 20,
        direction: direction || undefined,
        strength: strength || undefined,
        ticker: ticker || undefined,
        sector: effectiveSector || undefined,
      }),
    enabled: activeTab === "signals",
  });

  const { data: accuracyData } = useQuery({
    queryKey: ["signal-accuracy-summary"],
    queryFn: () => getSignalAccuracy({ window_days: 5 }),
    enabled: activeTab === "accuracy",
  });

  const handleSectorChange = (value: string) => {
    setPage(1);
    if (value) {
      setSearchParams({ sector: value });
    } else {
      setSearchParams({});
    }
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "signals", label: "Signals" },
    { key: "accuracy", label: "Accuracy" },
    { key: "methodology", label: "Methodology" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Signals</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-6">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === key
                  ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* Signals Tab */}
      {activeTab === "signals" && (
        <>
          {/* Filters */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 mb-6">
            <div className="flex flex-wrap gap-4">
              <input
                type="text"
                placeholder="Filter by ticker..."
                value={ticker}
                onChange={(e) => { setTicker(e.target.value); setPage(1); }}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              />
              <select
                value={effectiveSector}
                onChange={(e) => handleSectorChange(e.target.value)}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              >
                <option value="">All Sectors</option>
                {sectors?.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <select
                value={direction}
                onChange={(e) => { setDirection(e.target.value); setPage(1); }}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              >
                <option value="">All Directions</option>
                <option value="bullish">Bullish</option>
                <option value="bearish">Bearish</option>
                <option value="neutral">Neutral</option>
              </select>
              <select
                value={strength}
                onChange={(e) => { setStrength(e.target.value); setPage(1); }}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              >
                <option value="">All Strengths</option>
                <option value="strong">Strong</option>
                <option value="moderate">Moderate</option>
                <option value="weak">Weak</option>
              </select>
            </div>
          </div>

          {/* Signal Grid */}
          {isLoading ? (
            <LoadingSkeleton variant="card" count={6} />
          ) : data && data.data.length > 0 ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                {data.data.map((signal) => (
                  <SignalCard
                    key={signal.id}
                    signal={signal}
                    onDetailClick={setDetailSignal}
                  />
                ))}
              </div>

              {/* Pagination */}
              {data.meta.total_pages > 1 && (
                <div className="flex items-center justify-center gap-4">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    Page {data.meta.page} of {data.meta.total_pages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.min(data.meta.total_pages, p + 1))}
                    disabled={page >= data.meta.total_pages}
                    className="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          ) : (
            <p className="text-gray-500 dark:text-gray-400">
              No signals found{effectiveSector ? ` for ${effectiveSector} sector` : ""}. Signals will appear after the generation pipeline runs.
            </p>
          )}
        </>
      )}

      {/* Accuracy Tab */}
      {activeTab === "accuracy" && (
        <div className="space-y-8">
          {/* Summary */}
          {accuracyData && accuracyData.length > 0 && (() => {
            const summary = accuracyData[0]!;
            return (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Overall Accuracy (5-Day Window)
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {summary.accuracy_pct.toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Overall</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {summary.total_evaluated}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Evaluated</p>
                </div>
                {summary.bullish_accuracy_pct != null && (
                  <div className="text-center">
                    <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      {summary.bullish_accuracy_pct.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Bullish</p>
                  </div>
                )}
                {summary.bearish_accuracy_pct != null && (
                  <div className="text-center">
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                      {summary.bearish_accuracy_pct.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Bearish</p>
                  </div>
                )}
              </div>
            </div>
            );
          })()}

          {/* Trend */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Accuracy Trend
            </h2>
            <AccuracyTrendChart sectors={sectors} />
          </div>

          {/* Distribution */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Accuracy Distribution
            </h2>
            <AccuracyDistributionChart />
          </div>
        </div>
      )}

      {/* Methodology Tab */}
      {activeTab === "methodology" && (
        <div className="space-y-8">
          {/* Scoring Formula */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              Composite Signal Scoring
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Each stock is scored using 6 components that combine sentiment analysis with technical indicators.
              The composite score determines signal direction and strength.
            </p>
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 font-mono text-sm text-gray-800 dark:text-gray-200">
              composite = w1 * sentiment_momentum + w2 * sentiment_volume<br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w3 * price_momentum + w4 * volume_anomaly<br />
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w5 * rsi + w6 * trend
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Default Weights:</p>
                <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
                  <li>Sentiment Momentum: 30%</li>
                  <li>Sentiment Volume: 20%</li>
                  <li>Price Momentum: 15%</li>
                </ul>
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">&nbsp;</p>
                <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
                  <li>Volume Anomaly: 10%</li>
                  <li>RSI: 15%</li>
                  <li>Trend: 10%</li>
                </ul>
              </div>
            </div>
            <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
              <p className="font-medium text-gray-900 dark:text-white mb-1">Strength Thresholds:</p>
              <p>Strong: |score| &gt; 0.6 &nbsp;|&nbsp; Moderate: |score| &gt; 0.35 &nbsp;|&nbsp; Weak: otherwise</p>
            </div>
          </div>

          {/* Adaptive Weights */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Adaptive Weights by Sector
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              The system learns optimal weights per sector from signal outcome feedback.
              Weights that deviate from defaults are highlighted.
            </p>
            <WeightsTable />
          </div>
        </div>
      )}

      {/* Signal Detail Panel */}
      {detailSignal && (
        <SignalDetailPanel
          signal={detailSignal}
          onClose={() => setDetailSignal(null)}
        />
      )}
    </div>
  );
}
