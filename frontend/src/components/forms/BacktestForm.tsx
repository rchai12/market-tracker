import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listSectors } from "../../api/stocks";
import type { BacktestConfig } from "../../types";

interface BacktestFormProps {
  onSubmit: (config: BacktestConfig) => void;
  isSubmitting: boolean;
}

export default function BacktestForm({ onSubmit, isSubmitting }: BacktestFormProps) {
  const [targetType, setTargetType] = useState<"stock" | "sector">("stock");
  const [ticker, setTicker] = useState("");
  const [sectorName, setSectorName] = useState("");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [mode, setMode] = useState<"technical" | "full">("technical");
  const [capital, setCapital] = useState("10000");
  const [strength, setStrength] = useState<"moderate" | "strong">("moderate");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [commission, setCommission] = useState("0.1");
  const [slippage, setSlippage] = useState("0.05");
  const [positionSize, setPositionSize] = useState("100");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [benchmark, setBenchmark] = useState("SPY");

  const { data: sectors } = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
    staleTime: 5 * 60 * 1000,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const config: BacktestConfig = {
      start_date: startDate,
      end_date: endDate,
      starting_capital: parseFloat(capital) || 10000,
      mode,
      min_signal_strength: strength,
      commission_pct: (parseFloat(commission) || 0) / 100,
      slippage_pct: (parseFloat(slippage) || 0) / 100,
      position_size_pct: parseFloat(positionSize) || 100,
      stop_loss_pct: stopLoss ? parseFloat(stopLoss) : null,
      take_profit_pct: takeProfit ? parseFloat(takeProfit) : null,
      benchmark_ticker: benchmark || undefined,
    };
    if (targetType === "stock") {
      config.ticker = ticker.toUpperCase();
    } else {
      config.sector_name = sectorName;
    }
    onSubmit(config);
  };

  const inputClass =
    "w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Target type */}
        <div>
          <label className={labelClass}>Target</label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setTargetType("stock")}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                targetType === "stock"
                  ? "bg-blue-50 border-blue-500 text-blue-700 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-400"
                  : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              }`}
            >
              Stock
            </button>
            <button
              type="button"
              onClick={() => setTargetType("sector")}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                targetType === "sector"
                  ? "bg-blue-50 border-blue-500 text-blue-700 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-400"
                  : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              }`}
            >
              Sector
            </button>
          </div>
        </div>

        {/* Ticker or sector select */}
        <div>
          <label className={labelClass}>
            {targetType === "stock" ? "Ticker" : "Sector"}
          </label>
          {targetType === "stock" ? (
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="e.g. AAPL"
              required
              className={inputClass}
            />
          ) : (
            <select
              value={sectorName}
              onChange={(e) => setSectorName(e.target.value)}
              required
              className={inputClass}
            >
              <option value="">Select sector...</option>
              {sectors?.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Mode */}
        <div>
          <label className={labelClass}>Mode</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "technical" | "full")}
            className={inputClass}
          >
            <option value="technical">Technical (OHLCV only)</option>
            <option value="full">Full (+ Sentiment)</option>
          </select>
        </div>

        {/* Start date */}
        <div>
          <label className={labelClass}>Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
            className={inputClass}
          />
        </div>

        {/* End date */}
        <div>
          <label className={labelClass}>End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            required
            className={inputClass}
          />
        </div>

        {/* Starting capital */}
        <div>
          <label className={labelClass}>Starting Capital ($)</label>
          <input
            type="number"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            min={100}
            max={1000000}
            step={100}
            required
            className={inputClass}
          />
        </div>

        {/* Min signal strength */}
        <div>
          <label className={labelClass}>Min Signal Strength</label>
          <select
            value={strength}
            onChange={(e) => setStrength(e.target.value as "moderate" | "strong")}
            className={inputClass}
          >
            <option value="moderate">Moderate+</option>
            <option value="strong">Strong only</option>
          </select>
        </div>
      </div>

      {/* Advanced Settings */}
      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 flex items-center gap-1"
        >
          <svg
            className={`w-4 h-4 transition-transform ${showAdvanced ? "rotate-90" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Advanced Settings
        </button>

        {showAdvanced && (
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-3 border-t border-gray-200 dark:border-gray-700">
            <div>
              <label className={labelClass}>Commission (%)</label>
              <input
                type="number"
                value={commission}
                onChange={(e) => setCommission(e.target.value)}
                min={0}
                max={5}
                step={0.01}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Slippage (%)</label>
              <input
                type="number"
                value={slippage}
                onChange={(e) => setSlippage(e.target.value)}
                min={0}
                max={5}
                step={0.01}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Position Size (%)</label>
              <input
                type="number"
                value={positionSize}
                onChange={(e) => setPositionSize(e.target.value)}
                min={10}
                max={100}
                step={5}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Stop Loss (%)</label>
              <input
                type="number"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                min={0}
                max={50}
                step={0.5}
                placeholder="e.g. 5"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Take Profit (%)</label>
              <input
                type="number"
                value={takeProfit}
                onChange={(e) => setTakeProfit(e.target.value)}
                min={0}
                max={500}
                step={1}
                placeholder="e.g. 20"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Benchmark</label>
              <input
                type="text"
                value={benchmark}
                onChange={(e) => setBenchmark(e.target.value.toUpperCase())}
                placeholder="SPY"
                className={inputClass}
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {isSubmitting ? "Submitting..." : "Run Backtest"}
        </button>
      </div>
    </form>
  );
}
