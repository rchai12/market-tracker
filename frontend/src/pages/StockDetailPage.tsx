import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getStock } from "../api/stocks";
import { getDailyData } from "../api/marketData";
import { addToWatchlist, removeFromWatchlist, getWatchlist } from "../api/watchlist";
import { getTickerSentimentTimeline } from "../api/sentiment";
import { getSignalHistory } from "../api/signals";
import PriceChart from "../components/charts/PriceChart";
import VolumeChart from "../components/charts/VolumeChart";
import SentimentChart from "../components/sentiment/SentimentChart";
import SentimentBadge from "../components/sentiment/SentimentBadge";
import SignalCard from "../components/signals/SignalCard";

export default function StockDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const queryClient = useQueryClient();

  const { data: stock, isLoading: stockLoading } = useQuery({
    queryKey: ["stock", ticker],
    queryFn: () => getStock(ticker!),
    enabled: !!ticker,
  });

  const { data: marketData, isLoading: marketLoading } = useQuery({
    queryKey: ["market-data", ticker, "daily"],
    queryFn: () => getDailyData(ticker!, { limit: 365 }),
    enabled: !!ticker,
  });

  const { data: sentimentData } = useQuery({
    queryKey: ["sentiment-timeline", ticker],
    queryFn: () => getTickerSentimentTimeline(ticker!, 30),
    enabled: !!ticker,
  });

  const { data: signalData } = useQuery({
    queryKey: ["signals", ticker],
    queryFn: () => getSignalHistory(ticker!, 1, 5),
    enabled: !!ticker,
  });

  const { data: watchlist } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  const isInWatchlist = watchlist?.some((item) => item.ticker === ticker?.toUpperCase());

  const addMutation = useMutation({
    mutationFn: () => addToWatchlist(ticker!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const removeMutation = useMutation({
    mutationFn: () => removeFromWatchlist(ticker!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  if (stockLoading) {
    return <p className="text-gray-500 dark:text-gray-400">Loading...</p>;
  }

  if (!stock) {
    return <p className="text-red-500">Stock not found</p>;
  }

  // Compute latest sentiment from timeline data
  const latestSentiment = sentimentData && sentimentData.length > 0
    ? sentimentData[sentimentData.length - 1]
    : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {stock.ticker}
            </h1>
            {latestSentiment && (
              <SentimentBadge
                label={latestSentiment.dominant_label}
                score={Math.max(latestSentiment.avg_positive, latestSentiment.avg_negative, latestSentiment.avg_neutral)}
                size="md"
              />
            )}
          </div>
          <p className="text-gray-500 dark:text-gray-400">{stock.company_name}</p>
          {stock.sector_name && (
            <span className="inline-block mt-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-1 rounded">
              {stock.sector_name}
            </span>
          )}
        </div>
        <button
          onClick={() => isInWatchlist ? removeMutation.mutate() : addMutation.mutate()}
          disabled={addMutation.isPending || removeMutation.isPending}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            isInWatchlist
              ? "bg-red-50 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400"
              : "bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400"
          }`}
        >
          {isInWatchlist ? "Remove from Watchlist" : "Add to Watchlist"}
        </button>
      </div>

      {/* Price Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Price
        </h2>
        {marketLoading ? (
          <p className="text-gray-500 dark:text-gray-400 py-8 text-center">Loading chart...</p>
        ) : marketData && marketData.length > 0 ? (
          <PriceChart data={marketData} />
        ) : (
          <p className="text-gray-500 dark:text-gray-400 py-8 text-center">
            No market data yet. Data will appear after the first market data fetch.
          </p>
        )}
      </div>

      {/* Volume Chart */}
      {marketData && marketData.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Volume
          </h2>
          <VolumeChart data={marketData} />
        </div>
      )}

      {/* Sentiment + Signals */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Sentiment (30 days)
          </h2>
          {sentimentData && sentimentData.length > 0 ? (
            <SentimentChart data={sentimentData} height={180} />
          ) : (
            <p className="text-gray-500 dark:text-gray-400 text-sm py-4 text-center">
              No sentiment data yet. Data will appear after articles are analyzed.
            </p>
          )}
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Recent Signals
          </h2>
          {signalData && signalData.data.length > 0 ? (
            <div className="space-y-3">
              {signalData.data.map((signal) => (
                <SignalCard key={signal.id} signal={signal} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400 text-sm py-4 text-center">
              No signals yet. Signals will appear after the generation pipeline runs.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
