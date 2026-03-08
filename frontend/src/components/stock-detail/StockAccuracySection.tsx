import { useQuery } from "@tanstack/react-query";
import { getTickerAccuracy } from "../../api/signals";
import AccuracyBadge from "../signals/AccuracyBadge";
import Card from "../common/Card";

interface StockAccuracySectionProps {
  ticker: string;
}

export default function StockAccuracySection({ ticker }: StockAccuracySectionProps) {
  const { data: accuracyData } = useQuery({
    queryKey: ["ticker-accuracy", ticker],
    queryFn: () => getTickerAccuracy(ticker),
  });

  if (!accuracyData || accuracyData.length === 0) return null;

  return (
    <Card className="mt-4">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
        Signal Accuracy
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {accuracyData.map((acc) => (
          <div key={acc.window_days} className="text-center rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {acc.window_days}-Day Window
            </p>
            <AccuracyBadge accuracy={acc.accuracy_pct} size="md" />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {acc.correct_count}/{acc.total_evaluated} correct
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}
