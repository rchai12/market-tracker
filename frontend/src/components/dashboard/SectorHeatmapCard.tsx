import { Link } from "react-router-dom";
import type { SentimentSummary } from "../../types";
import SentimentBadge from "../sentiment/SentimentBadge";

interface SectorHeatmapCardProps {
  sector: SentimentSummary;
}

function getSentimentBackground(s: SentimentSummary): string {
  if (s.dominant_label === "positive") {
    if (s.avg_positive >= 0.6) return "bg-green-100 dark:bg-green-900/40";
    if (s.avg_positive >= 0.4) return "bg-green-50 dark:bg-green-900/20";
    return "bg-green-50/50 dark:bg-green-900/10";
  }
  if (s.dominant_label === "negative") {
    if (s.avg_negative >= 0.6) return "bg-red-100 dark:bg-red-900/40";
    if (s.avg_negative >= 0.4) return "bg-red-50 dark:bg-red-900/20";
    return "bg-red-50/50 dark:bg-red-900/10";
  }
  return "bg-gray-50 dark:bg-gray-800";
}

export default function SectorHeatmapCard({ sector }: SectorHeatmapCardProps) {
  const bg = getSentimentBackground(sector);

  return (
    <Link
      to={`/signals?sector=${encodeURIComponent(sector.sector)}`}
      className={`rounded-xl p-4 border border-gray-200 dark:border-gray-700 ${bg} block hover:border-blue-400 dark:hover:border-blue-500 transition-colors`}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
          {sector.sector}
        </h3>
        <SentimentBadge label={sector.dominant_label} size="sm" />
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
        <div>
          <p className="font-semibold text-green-700 dark:text-green-400">
            {sector.positive_count}
          </p>
          <p className="text-gray-500 dark:text-gray-400">Positive</p>
        </div>
        <div>
          <p className="font-semibold text-red-700 dark:text-red-400">
            {sector.negative_count}
          </p>
          <p className="text-gray-500 dark:text-gray-400">Negative</p>
        </div>
        <div>
          <p className="font-semibold text-gray-600 dark:text-gray-300">
            {sector.neutral_count}
          </p>
          <p className="text-gray-500 dark:text-gray-400">Neutral</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>{sector.total_articles} articles</span>
        <span>
          +{(sector.avg_positive * 100).toFixed(0)}% / −{(sector.avg_negative * 100).toFixed(0)}%
        </span>
      </div>
    </Link>
  );
}
