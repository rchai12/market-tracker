import type { Signal } from "../../types";

interface ComponentBreakdownProps {
  signal: Signal;
}

const COMPONENTS = [
  { key: "sentiment_score", label: "Sentiment" },
  { key: "sentiment_volume_score", label: "Sent. Volume" },
  { key: "price_score", label: "Price" },
  { key: "volume_score", label: "Volume" },
  { key: "rsi_score", label: "RSI" },
  { key: "trend_score", label: "Trend" },
] as const;

export default function ComponentBreakdown({ signal }: ComponentBreakdownProps) {
  return (
    <div className="space-y-1.5 pt-3 border-t border-gray-200 dark:border-gray-700">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
        Component Scores
      </p>
      {COMPONENTS.map(({ key, label }) => {
        const value = signal[key];
        if (value == null) return null;

        const pct = Math.abs(value) * 100;
        const isPositive = value >= 0;

        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span className="w-20 text-gray-600 dark:text-gray-400 shrink-0">{label}</span>
            <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-700 rounded-full relative overflow-hidden">
              <div className="absolute inset-0 flex items-center">
                <div className="w-1/2" />
                <div className="w-px h-full bg-gray-300 dark:bg-gray-600" />
                <div className="w-1/2" />
              </div>
              {isPositive ? (
                <div
                  className="absolute top-0 h-full bg-emerald-500 dark:bg-emerald-400 rounded-r-full"
                  style={{ left: "50%", width: `${Math.min(pct, 100) / 2}%` }}
                />
              ) : (
                <div
                  className="absolute top-0 h-full bg-red-500 dark:bg-red-400 rounded-l-full"
                  style={{ right: "50%", width: `${Math.min(pct, 100) / 2}%` }}
                />
              )}
            </div>
            <span className={`w-12 text-right font-mono ${isPositive ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
              {value > 0 ? "+" : ""}{value.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
