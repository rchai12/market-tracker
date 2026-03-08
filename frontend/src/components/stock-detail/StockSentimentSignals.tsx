import { useQuery } from "@tanstack/react-query";
import { getTickerSentimentTimeline } from "../../api/sentiment";
import { getSignalHistory } from "../../api/signals";
import SentimentChart from "../sentiment/SentimentChart";
import SignalCard from "../signals/SignalCard";
import Card from "../common/Card";

interface StockSentimentSignalsProps {
  ticker: string;
}

export default function StockSentimentSignals({ ticker }: StockSentimentSignalsProps) {
  const { data: sentimentData } = useQuery({
    queryKey: ["sentiment-timeline", ticker],
    queryFn: () => getTickerSentimentTimeline(ticker, 30),
  });

  const { data: signalData } = useQuery({
    queryKey: ["signals", ticker],
    queryFn: () => getSignalHistory(ticker, 1, 5),
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Sentiment (30 days)
        </h2>
        {sentimentData && sentimentData.length > 0 ? (
          <SentimentChart data={sentimentData} height={180} />
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-sm py-4 text-center">
            No sentiment data yet. Data will appear after articles are analyzed.
          </p>
        )}
      </Card>
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Recent Signals
        </h2>
        {signalData && signalData.data.length > 0 ? (
          <div className="space-y-3">
            {signalData.data.map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-sm py-4 text-center">
            No signals yet. Signals will appear after the generation pipeline runs.
          </p>
        )}
      </Card>
    </div>
  );
}
