import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getSectorSentiment, getTrendingSentiment } from "../api/sentiment";
import SentimentBadge from "../components/sentiment/SentimentBadge";

export default function SentimentPage() {
  const { data: sectors, isLoading: sectorsLoading } = useQuery({
    queryKey: ["sentiment-sectors"],
    queryFn: () => getSectorSentiment(7),
  });

  const { data: trending, isLoading: trendingLoading } = useQuery({
    queryKey: ["sentiment-trending"],
    queryFn: () => getTrendingSentiment(3, 10),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
        Sentiment Analysis
      </h1>

      {/* Sector Sentiment */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Sector Sentiment (7 days)
        </h2>
        {sectorsLoading ? (
          <p className="text-gray-500 dark:text-gray-400">Loading...</p>
        ) : sectors && sectors.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sectors.map((sector) => (
              <Link
                key={sector.sector}
                to={`/signals?sector=${encodeURIComponent(sector.sector || "")}`}
                className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 block hover:border-blue-400 dark:hover:border-blue-500 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-gray-900 dark:text-white">
                    {sector.sector}
                  </h3>
                  <SentimentBadge label={sector.dominant_label} size="md" />
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="text-center">
                    <p className="text-green-600 dark:text-green-400 font-semibold">
                      {sector.positive_count}
                    </p>
                    <p className="text-gray-500 dark:text-gray-400 text-xs">Positive</p>
                  </div>
                  <div className="text-center">
                    <p className="text-red-600 dark:text-red-400 font-semibold">
                      {sector.negative_count}
                    </p>
                    <p className="text-gray-500 dark:text-gray-400 text-xs">Negative</p>
                  </div>
                  <div className="text-center">
                    <p className="text-gray-600 dark:text-gray-300 font-semibold">
                      {sector.neutral_count}
                    </p>
                    <p className="text-gray-500 dark:text-gray-400 text-xs">Neutral</p>
                  </div>
                </div>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                  {sector.total_articles} articles analyzed
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400">
            No sentiment data yet. Data will appear after articles are processed.
          </p>
        )}
      </div>

      {/* Trending Stocks by Sentiment */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Trending by Sentiment (3 days)
        </h2>
        {trendingLoading ? (
          <p className="text-gray-500 dark:text-gray-400">Loading...</p>
        ) : trending && trending.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Ticker</th>
                  <th className="text-center py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Articles</th>
                  <th className="text-center py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Sentiment</th>
                  <th className="text-center py-2 px-3 text-green-600 dark:text-green-400 font-medium">Pos</th>
                  <th className="text-center py-2 px-3 text-red-600 dark:text-red-400 font-medium">Neg</th>
                  <th className="text-center py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Neu</th>
                </tr>
              </thead>
              <tbody>
                {trending.map((item) => (
                  <tr
                    key={item.ticker}
                    className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30"
                  >
                    <td className="py-2 px-3 font-medium">
                      <Link
                        to={`/stocks/${item.ticker}`}
                        className="text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {item.ticker}
                      </Link>
                    </td>
                    <td className="py-2 px-3 text-center text-gray-600 dark:text-gray-300">
                      {item.total_articles}
                    </td>
                    <td className="py-2 px-3 text-center">
                      <SentimentBadge label={item.dominant_label} />
                    </td>
                    <td className="py-2 px-3 text-center text-green-600 dark:text-green-400">
                      {(item.avg_positive * 100).toFixed(0)}%
                    </td>
                    <td className="py-2 px-3 text-center text-red-600 dark:text-red-400">
                      {(item.avg_negative * 100).toFixed(0)}%
                    </td>
                    <td className="py-2 px-3 text-center text-gray-500 dark:text-gray-400">
                      {(item.avg_neutral * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400">
            No trending sentiment data yet. Data will appear after articles are processed.
          </p>
        )}
      </div>
    </div>
  );
}
