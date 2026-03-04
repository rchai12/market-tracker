interface ArticleActivityCardProps {
  sources: { source: string; count: number }[];
}

const SOURCE_LABELS: Record<string, string> = {
  yahoo_finance: "Yahoo Finance",
  finviz: "Finviz",
  reuters_rss: "Reuters",
  sec_edgar: "SEC EDGAR",
  marketwatch: "MarketWatch",
  reddit: "Reddit",
  fred: "FRED",
};

function humanizeSource(source: string): string {
  return SOURCE_LABELS[source] ?? source.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ArticleActivityCard({ sources }: ArticleActivityCardProps) {
  const sorted = [...sources].sort((a, b) => b.count - a.count);
  const maxCount = sorted.length > 0 ? sorted[0].count : 1;
  const total = sorted.reduce((sum, s) => sum + s.count, 0);

  return (
    <div>
      <div className="space-y-3">
        {sorted.map((s) => (
          <div key={s.source} className="flex items-center gap-3">
            <span className="text-xs text-gray-600 dark:text-gray-300 w-28 text-right truncate">
              {humanizeSource(s.source)}
            </span>
            <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 dark:bg-blue-400 rounded-full"
                style={{ width: `${(s.count / maxCount) * 100}%` }}
              />
            </div>
            <span className="text-xs font-mono text-gray-500 dark:text-gray-400 w-10 text-right">
              {s.count}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 text-right">
        Total: {total.toLocaleString()} articles
      </p>
    </div>
  );
}
