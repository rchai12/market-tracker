import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import type { MarketDataDaily } from "../../types";
import { getChartThemeOptions } from "../../utils/chartConfig";

interface PriceChartProps {
  data: MarketDataDaily[];
  height?: number;
}

export default function PriceChart({ data, height = 400 }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const isDark = document.documentElement.classList.contains("dark");

    const chart = createChart(chartContainerRef.current, {
      ...getChartThemeOptions(isDark),
      width: chartContainerRef.current.clientWidth,
      height,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || !data.length) return;

    const chartData = data.map((d) => ({
      time: d.date as string,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    seriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" />
  );
}
