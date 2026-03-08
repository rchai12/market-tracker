import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDailyData, getIndicators } from "../../api/marketData";
import PriceChart from "../charts/PriceChart";
import VolumeChart from "../charts/VolumeChart";
import RSIChart from "../charts/RSIChart";
import MACDChart from "../charts/MACDChart";
import LoadingSkeleton from "../common/LoadingSkeleton";
import Card from "../common/Card";

interface StockPriceSectionProps {
  ticker: string;
}

export default function StockPriceSection({ ticker }: StockPriceSectionProps) {
  const [showSMA, setShowSMA] = useState(false);
  const [showBollinger, setShowBollinger] = useState(false);
  const [showRSI, setShowRSI] = useState(false);
  const [showMACD, setShowMACD] = useState(false);

  const { data: marketData, isLoading: marketLoading } = useQuery({
    queryKey: ["market-data", ticker, "daily"],
    queryFn: () => getDailyData(ticker, { limit: 365 }),
  });

  const { data: indicatorData } = useQuery({
    queryKey: ["indicators", ticker],
    queryFn: () => getIndicators(ticker, { days: 365 }),
  });

  return (
    <>
      {/* Price Chart */}
      <Card className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Price
          </h2>
          {marketData && marketData.length > 0 && indicatorData && (
            <div className="flex gap-2">
              {(["SMA", "Bollinger", "RSI", "MACD"] as const).map((label) => {
                const active = label === "SMA" ? showSMA : label === "Bollinger" ? showBollinger : label === "RSI" ? showRSI : showMACD;
                const toggle = label === "SMA" ? setShowSMA : label === "Bollinger" ? setShowBollinger : label === "RSI" ? setShowRSI : setShowMACD;
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => toggle((v) => !v)}
                    className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
                      active
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {marketLoading ? (
          <LoadingSkeleton variant="chart" count={1} />
        ) : marketData && marketData.length > 0 ? (
          <PriceChart
            data={marketData}
            indicators={indicatorData}
            showSMA={showSMA}
            showBollinger={showBollinger}
          />
        ) : (
          <p className="text-gray-500 dark:text-gray-400 py-8 text-center">
            No market data yet. Data will appear after the first market data fetch.
          </p>
        )}
      </Card>

      {/* RSI Chart */}
      {showRSI && indicatorData && indicatorData.length > 0 && (
        <Card className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            RSI (14)
          </h2>
          <RSIChart data={indicatorData} />
        </Card>
      )}

      {/* MACD Chart */}
      {showMACD && indicatorData && indicatorData.length > 0 && (
        <Card className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            MACD (12, 26, 9)
          </h2>
          <MACDChart data={indicatorData} />
        </Card>
      )}

      {/* Volume Chart */}
      {marketData && marketData.length > 0 && (
        <Card className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Volume
          </h2>
          <VolumeChart data={marketData} />
        </Card>
      )}
    </>
  );
}
