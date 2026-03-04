import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listSignals } from "../api/signals";
import SignalCard from "../components/signals/SignalCard";
import LoadingSkeleton from "../components/common/LoadingSkeleton";

export default function SignalsPage() {
  const [page, setPage] = useState(1);
  const [direction, setDirection] = useState<string>("");
  const [strength, setStrength] = useState<string>("");
  const [ticker, setTicker] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["signals", page, direction, strength, ticker],
    queryFn: () =>
      listSignals({
        page,
        per_page: 20,
        direction: direction || undefined,
        strength: strength || undefined,
        ticker: ticker || undefined,
      }),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Signals</h1>

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
              <SignalCard key={signal.id} signal={signal} />
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
          No signals yet. Signals will appear after the generation pipeline runs.
        </p>
      )}
    </div>
  );
}
