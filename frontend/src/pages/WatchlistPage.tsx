import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getWatchlist, type WatchlistItem } from "../api/watchlist";
import { getDailyData } from "../api/marketData";
import { getSignalHistory } from "../api/signals";
import SparklineChart from "../components/charts/SparklineChart";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorRetry from "../components/common/ErrorRetry";
import { DIRECTION_COLORS } from "../constants/ui";

function WatchlistCard({ item }: { item: WatchlistItem }) {
  const { data: marketData } = useQuery({
    queryKey: ["market-data", item.ticker, "sparkline"],
    queryFn: () => getDailyData(item.ticker, { limit: 30 }),
    staleTime: 10 * 60 * 1000,
  });

  const { data: signalData } = useQuery({
    queryKey: ["signals", item.ticker, "latest-1"],
    queryFn: () => getSignalHistory(item.ticker, 1, 1),
    staleTime: 10 * 60 * 1000,
  });

  const latestSignal = signalData?.data?.[0] ?? null;

  return (
    <Link to={`/stocks/${item.ticker}`} className="block">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 hover:shadow-md transition-shadow">
        <div className="flex justify-between items-start">
          <div>
            <p className="font-bold text-gray-900 dark:text-white">{item.ticker}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">{item.company_name}</p>
          </div>
          <div className="flex items-center gap-2">
            {item.sector_name && (
              <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-1 rounded">
                {item.sector_name}
              </span>
            )}
            {latestSignal && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  DIRECTION_COLORS[latestSignal.direction]?.bg ?? ""
                } ${DIRECTION_COLORS[latestSignal.direction]?.text ?? ""}`}
              >
                {latestSignal.direction}
              </span>
            )}
          </div>
        </div>
        <div className="mt-3">
          {marketData && marketData.length > 1 ? (
            <SparklineChart data={marketData} height={40} />
          ) : (
            <div className="h-10 bg-gray-100 dark:bg-gray-700/50 rounded animate-pulse" />
          )}
        </div>
      </div>
    </Link>
  );
}

export default function WatchlistPage() {
  const { data: items, isLoading, isError, refetch } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Watchlist</h1>
      {isLoading ? (
        <LoadingSkeleton variant="card" count={3} />
      ) : isError ? (
        <ErrorRetry message="Failed to load watchlist" onRetry={() => refetch()} />
      ) : items && items.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <WatchlistCard key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <p className="text-gray-500 dark:text-gray-400">
          No stocks in your watchlist. Add tickers from the stock detail page.
        </p>
      )}
    </div>
  );
}
