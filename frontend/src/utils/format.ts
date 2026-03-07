/** Shared formatting utilities. */

export function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export const SOURCE_LABELS: Record<string, string> = {
  yahoo_finance: "Yahoo Finance",
  finviz: "Finviz",
  google_news: "Google News",
  sec_edgar: "SEC EDGAR",
  marketwatch: "MarketWatch",
  reddit_stocks: "Reddit (stocks)",
  reddit_wallstreetbets: "Reddit (WSB)",
  fred: "FRED",
};

export function humanizeSource(source: string): string {
  return SOURCE_LABELS[source] ?? source.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
