interface SourceCredibilityIndicatorProps {
  source: string;
  showLabel?: boolean;
}

const SOURCE_CREDIBILITY: Record<string, number> = {
  sec_edgar: 1.0,
  fred: 0.9,
  reuters_rss: 0.9,
  marketwatch: 0.8,
  yahoo_finance: 0.75,
  finviz: 0.7,
  google_news: 0.65,
  reddit_stocks: 0.4,
  reddit_wallstreetbets: 0.35,
};

function getColor(score: number): string {
  if (score >= 0.8) return "bg-green-500";
  if (score >= 0.6) return "bg-yellow-500";
  return "bg-red-500";
}

function getLabel(score: number): string {
  if (score >= 0.8) return "High";
  if (score >= 0.6) return "Medium";
  return "Low";
}

export default function SourceCredibilityIndicator({ source, showLabel = false }: SourceCredibilityIndicatorProps) {
  const score = SOURCE_CREDIBILITY[source] ?? 0.5;
  const color = getColor(score);
  const label = getLabel(score);

  return (
    <span className="inline-flex items-center gap-1" title={`Source credibility: ${(score * 100).toFixed(0)}%`}>
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
      {showLabel && (
        <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
      )}
    </span>
  );
}
