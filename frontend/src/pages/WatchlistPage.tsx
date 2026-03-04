import { useQuery } from "@tanstack/react-query";
import { getWatchlist } from "../api/watchlist";

export default function WatchlistPage() {
  const { data: items, isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Watchlist</h1>
      {isLoading ? (
        <p className="text-gray-500 dark:text-gray-400">Loading...</p>
      ) : items && items.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white dark:bg-gray-800 rounded-xl shadow p-4"
            >
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-bold text-gray-900 dark:text-white">{item.ticker}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{item.company_name}</p>
                </div>
                {item.sector_name && (
                  <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-1 rounded">
                    {item.sector_name}
                  </span>
                )}
              </div>
            </div>
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
