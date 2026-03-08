import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getStock } from "../api/stocks";
import { addToWatchlist, removeFromWatchlist, getWatchlist } from "../api/watchlist";
import { getTickerSentimentTimeline } from "../api/sentiment";
import SentimentBadge from "../components/sentiment/SentimentBadge";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import StockPriceSection from "../components/stock-detail/StockPriceSection";
import StockSentimentSignals from "../components/stock-detail/StockSentimentSignals";
import StockAccuracySection from "../components/stock-detail/StockAccuracySection";
import StockOptionsSection from "../components/stock-detail/StockOptionsSection";
import StockArticlesSection from "../components/stock-detail/StockArticlesSection";

export default function StockDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const queryClient = useQueryClient();

  const { data: stock, isLoading: stockLoading } = useQuery({
    queryKey: ["stock", ticker],
    queryFn: () => getStock(ticker!),
    enabled: !!ticker,
  });

  const { data: sentimentData } = useQuery({
    queryKey: ["sentiment-timeline", ticker],
    queryFn: () => getTickerSentimentTimeline(ticker!, 30),
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
    return <LoadingSkeleton variant="card" count={3} />;
  }

  if (!stock) {
    return <p className="text-red-500">Stock not found</p>;
  }

  const latestSentiment = sentimentData && sentimentData.length > 0
    ? sentimentData[sentimentData.length - 1]
    : null;

  return (
    <div>
      {/* Header */}
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
          type="button"
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

      <StockPriceSection ticker={ticker!} />
      <StockSentimentSignals ticker={ticker!} />
      <StockOptionsSection ticker={ticker!} />
      <StockAccuracySection ticker={ticker!} />
      <StockArticlesSection ticker={ticker!} />
    </div>
  );
}
