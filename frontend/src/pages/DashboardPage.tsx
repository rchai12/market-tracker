import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getLatestSignals, getSignalAccuracy } from "../api/signals";
import { getSectorSentiment } from "../api/sentiment";
import { listSources } from "../api/articles";
import AccuracyCard from "../components/dashboard/AccuracyCard";
import SignalCard from "../components/signals/SignalCard";
import SectorHeatmapCard from "../components/dashboard/SectorHeatmapCard";
import TopMoversCard from "../components/dashboard/TopMoversCard";
import ArticleActivityCard from "../components/dashboard/ArticleActivityCard";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorRetry from "../components/common/ErrorRetry";
import Card from "../components/common/Card";

export default function DashboardPage() {
  const {
    data: signals,
    isLoading: signalsLoading,
    isError: signalsError,
    refetch: refetchSignals,
  } = useQuery({
    queryKey: ["dashboard-signals"],
    queryFn: () => getLatestSignals(20, "moderate"),
  });

  const {
    data: sectors,
    isLoading: sectorsLoading,
    isError: sectorsError,
    refetch: refetchSectors,
  } = useQuery({
    queryKey: ["dashboard-sectors"],
    queryFn: () => getSectorSentiment(7),
  });

  const {
    data: sources,
    isLoading: sourcesLoading,
    isError: sourcesError,
    refetch: refetchSources,
  } = useQuery({
    queryKey: ["dashboard-sources"],
    queryFn: listSources,
  });

  const {
    data: accuracy,
    isLoading: accuracyLoading,
    isError: accuracyError,
    refetch: refetchAccuracy,
  } = useQuery({
    queryKey: ["dashboard-accuracy"],
    queryFn: () => getSignalAccuracy({ window_days: 5 }),
  });

  const displaySignals = useMemo(() => (signals ?? []).slice(0, 10), [signals]);

  const bullishSignals = useMemo(
    () =>
      (signals ?? [])
        .filter((s) => s.direction === "bullish")
        .sort((a, b) => b.composite_score - a.composite_score)
        .slice(0, 5),
    [signals]
  );

  const bearishSignals = useMemo(
    () =>
      (signals ?? [])
        .filter((s) => s.direction === "bearish")
        .sort((a, b) => a.composite_score - b.composite_score)
        .slice(0, 5),
    [signals]
  );

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Dashboard</h1>

      {/* Latest Signals */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Latest Signals
        </h2>
        {signalsLoading ? (
          <LoadingSkeleton variant="card" count={3} />
        ) : signalsError ? (
          <ErrorRetry onRetry={() => refetchSignals()} />
        ) : displaySignals.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {displaySignals.map((s) => (
              <SignalCard key={s.id} signal={s} />
            ))}
          </div>
        ) : (
          <Card padding="md" className="text-center">
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              No signals yet. Signals will appear after the generation pipeline runs.
            </p>
          </Card>
        )}
      </section>

      {/* Signal Accuracy */}
      <Card className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Signal Accuracy
        </h2>
        {accuracyLoading ? (
          <LoadingSkeleton variant="row" count={2} />
        ) : accuracyError ? (
          <ErrorRetry onRetry={() => refetchAccuracy()} />
        ) : (
          <AccuracyCard data={accuracy ?? []} />
        )}
      </Card>

      {/* Sector Heatmap + Top Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Sector Sentiment
          </h2>
          {sectorsLoading ? (
            <LoadingSkeleton variant="card" count={2} />
          ) : sectorsError ? (
            <ErrorRetry onRetry={() => refetchSectors()} />
          ) : sectors && sectors.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sectors.map((s) => (
                <SectorHeatmapCard key={s.sector} sector={s} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
              No sector data yet. Data will appear after sentiment analysis runs.
            </p>
          )}
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Top Movers
          </h2>
          {signalsLoading ? (
            <LoadingSkeleton variant="row" count={10} />
          ) : signalsError ? (
            <ErrorRetry onRetry={() => refetchSignals()} />
          ) : bullishSignals.length > 0 || bearishSignals.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-medium text-green-600 dark:text-green-400 mb-2">
                  Top Bullish
                </h3>
                {bullishSignals.length > 0 ? (
                  bullishSignals.map((s, i) => (
                    <TopMoversCard key={s.id} signal={s} rank={i + 1} />
                  ))
                ) : (
                  <p className="text-xs text-gray-400 dark:text-gray-500 py-2">
                    No bullish signals
                  </p>
                )}
              </div>
              <div>
                <h3 className="text-sm font-medium text-red-600 dark:text-red-400 mb-2">
                  Top Bearish
                </h3>
                {bearishSignals.length > 0 ? (
                  bearishSignals.map((s, i) => (
                    <TopMoversCard key={s.id} signal={s} rank={i + 1} />
                  ))
                ) : (
                  <p className="text-xs text-gray-400 dark:text-gray-500 py-2">
                    No bearish signals
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
              No signals yet. Top movers will appear after signal generation runs.
            </p>
          )}
        </Card>
      </div>

      {/* Article Activity */}
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Article Activity
        </h2>
        {sourcesLoading ? (
          <LoadingSkeleton variant="row" count={5} />
        ) : sourcesError ? (
          <ErrorRetry onRetry={() => refetchSources()} />
        ) : sources && sources.length > 0 ? (
          <ArticleActivityCard sources={sources} />
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
            No articles scraped yet. Data will appear after scrapers run.
          </p>
        )}
      </Card>
    </div>
  );
}
