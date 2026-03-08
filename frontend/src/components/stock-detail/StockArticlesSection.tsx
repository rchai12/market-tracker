import { useQuery } from "@tanstack/react-query";
import { getTickerSentimentArticles } from "../../api/sentiment";
import { humanizeSource, formatTimeAgo } from "../../utils/format";
import SentimentBadge from "../sentiment/SentimentBadge";
import EventCategoryBadge from "../articles/EventCategoryBadge";
import SourceCredibilityIndicator from "../articles/SourceCredibilityIndicator";
import Card from "../common/Card";
import QueryGuard from "../common/QueryGuard";

interface StockArticlesSectionProps {
  ticker: string;
}

export default function StockArticlesSection({ ticker }: StockArticlesSectionProps) {
  const { data: articlesData, isLoading, isError, refetch } = useQuery({
    queryKey: ["sentiment-articles", ticker],
    queryFn: () => getTickerSentimentArticles(ticker, 1, 10),
  });

  return (
    <Card className="mt-4">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
        Recent Articles
      </h2>
      <QueryGuard
        data={articlesData}
        isLoading={isLoading}
        isError={isError}
        refetch={refetch}
        loadingVariant="row"
        loadingCount={5}
        emptyMessage="No articles yet. Articles will appear after news is scraped and analyzed."
        isEmpty={(d) => d.data.length === 0}
      >
        {(data) => (
          <div className="space-y-2">
            {data.data.map((score) => (
              <div
                key={score.id}
                className="flex items-start gap-3 py-2 border-b border-gray-100 dark:border-gray-700 last:border-0"
              >
                <SentimentBadge label={score.label} size="sm" />
                <div className="flex-1 min-w-0">
                  {score.article_source_url ? (
                    <a
                      href={score.article_source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 line-clamp-2"
                    >
                      {score.article_title || "Untitled"}
                    </a>
                  ) : (
                    <p className="text-sm text-gray-900 dark:text-white line-clamp-2">
                      {score.article_title || "Untitled"}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {score.article_source && (
                      <>
                        <SourceCredibilityIndicator source={score.article_source} />
                        <span>{humanizeSource(score.article_source)}</span>
                      </>
                    )}
                    {score.article_event_category && (
                      <EventCategoryBadge category={score.article_event_category} />
                    )}
                    <span>{formatTimeAgo(score.processed_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </QueryGuard>
    </Card>
  );
}
