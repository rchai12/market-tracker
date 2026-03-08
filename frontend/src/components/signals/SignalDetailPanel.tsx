import { useQuery } from "@tanstack/react-query";
import type { Signal, SignalDetail } from "../../types";
import { getSignalDetail } from "../../api/signals";
import { DIRECTION_COLORS } from "../../constants/ui";
import { formatTimeAgo, humanizeSource } from "../../utils/format";
import ComponentBreakdown from "./ComponentBreakdown";
import SentimentBadge from "../sentiment/SentimentBadge";
import LoadingSkeleton from "../common/LoadingSkeleton";

interface SignalDetailPanelProps {
  signal: Signal;
  onClose: () => void;
}

export default function SignalDetailPanel({ signal, onClose }: SignalDetailPanelProps) {
  const { data, isLoading } = useQuery<SignalDetail>({
    queryKey: ["signal-detail", signal.id],
    queryFn: () => getSignalDetail(signal.id),
  });

  const dirColors = DIRECTION_COLORS[signal.direction] ?? DIRECTION_COLORS.neutral!;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white dark:bg-gray-900 shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {signal.ticker} Signal
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {formatTimeAgo(signal.generated_at)}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${dirColors.bg} ${dirColors.text}`}>
              {signal.direction}
            </span>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="px-6 py-4 space-y-6">
          {/* Score + Strength */}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {signal.composite_score.toFixed(3)}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Composite Score</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white capitalize">
                {signal.strength}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Strength</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {signal.article_count}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Articles</p>
            </div>
          </div>

          {/* Reasoning */}
          {signal.reasoning && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Reasoning</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">{signal.reasoning}</p>
            </div>
          )}

          {/* Component Breakdown */}
          <ComponentBreakdown signal={signal} />

          {isLoading ? (
            <LoadingSkeleton variant="row" count={6} />
          ) : data ? (
            <>
              {/* Outcomes */}
              {data.outcomes.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Signal Outcomes
                  </h3>
                  <div className="grid grid-cols-3 gap-3">
                    {data.outcomes.map((o) => {
                      const isPositiveReturn = o.price_change_pct >= 0;
                      return (
                        <div
                          key={o.window_days}
                          className={`rounded-lg p-3 text-center ${
                            o.is_correct
                              ? "bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800"
                              : "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"
                          }`}
                        >
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{o.window_days}-Day</p>
                          <p className={`text-lg font-bold ${
                            isPositiveReturn
                              ? "text-emerald-600 dark:text-emerald-400"
                              : "text-red-600 dark:text-red-400"
                          }`}>
                            {isPositiveReturn ? "+" : ""}{(o.price_change_pct * 100).toFixed(2)}%
                          </p>
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium mt-1 ${
                            o.is_correct
                              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
                              : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
                          }`}>
                            {o.is_correct ? "Correct" : "Wrong"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Linked Articles */}
              {data.linked_articles.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Linked Articles ({data.linked_articles.length})
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {data.linked_articles.map((article) => (
                      <div
                        key={article.id}
                        className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            {article.url ? (
                              <a
                                href={article.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline line-clamp-2"
                              >
                                {article.title}
                              </a>
                            ) : (
                              <p className="text-sm font-medium text-gray-900 dark:text-white line-clamp-2">
                                {article.title}
                              </p>
                            )}
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {humanizeSource(article.source)}
                              </span>
                              {article.published_at && (
                                <span className="text-xs text-gray-400 dark:text-gray-500">
                                  {formatTimeAgo(article.published_at)}
                                </span>
                              )}
                            </div>
                          </div>
                          {article.sentiment_label && (
                            <SentimentBadge label={article.sentiment_label} />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {data.outcomes.length === 0 && data.linked_articles.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                  No outcomes or articles available yet.
                </p>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
