import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi, LineStyle } from "lightweight-charts";
import type { IndicatorData, MarketDataDaily } from "../../types";
import { getChartThemeOptions } from "../../utils/chartConfig";

interface PriceChartProps {
  data: MarketDataDaily[];
  indicators?: IndicatorData[];
  showSMA?: boolean;
  showBollinger?: boolean;
  height?: number;
}

export default function PriceChart({
  data,
  indicators,
  showSMA = false,
  showBollinger = false,
  height = 400,
}: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const overlaySeriesRef = useRef<ISeriesApi<"Line">[]>([]);

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
    if (!seriesRef.current || !chartRef.current || !data.length) return;

    const chart = chartRef.current;

    // Remove old overlay series
    for (const s of overlaySeriesRef.current) {
      chart.removeSeries(s);
    }
    overlaySeriesRef.current = [];

    // Set candlestick data
    const chartData = data.map((d) => ({
      time: d.date as string,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    seriesRef.current.setData(chartData);

    // Add indicator overlays
    if (indicators && indicators.length > 0) {
      if (showSMA) {
        const sma20Series = chart.addLineSeries({
          color: "#3b82f6",
          lineWidth: 1,
          title: "SMA 20",
        });
        sma20Series.setData(
          indicators
            .filter((d) => d.sma20 !== null)
            .map((d) => ({ time: d.date as string, value: d.sma20! }))
        );
        overlaySeriesRef.current.push(sma20Series);

        const sma50Series = chart.addLineSeries({
          color: "#f97316",
          lineWidth: 1,
          title: "SMA 50",
        });
        sma50Series.setData(
          indicators
            .filter((d) => d.sma50 !== null)
            .map((d) => ({ time: d.date as string, value: d.sma50! }))
        );
        overlaySeriesRef.current.push(sma50Series);
      }

      if (showBollinger) {
        const bbUpper = chart.addLineSeries({
          color: "#a855f7",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          title: "BB Upper",
        });
        bbUpper.setData(
          indicators
            .filter((d) => d.bb_upper !== null)
            .map((d) => ({ time: d.date as string, value: d.bb_upper! }))
        );
        overlaySeriesRef.current.push(bbUpper);

        const bbMiddle = chart.addLineSeries({
          color: "#a855f7",
          lineWidth: 1,
          title: "BB Mid",
        });
        bbMiddle.setData(
          indicators
            .filter((d) => d.bb_middle !== null)
            .map((d) => ({ time: d.date as string, value: d.bb_middle! }))
        );
        overlaySeriesRef.current.push(bbMiddle);

        const bbLower = chart.addLineSeries({
          color: "#a855f7",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          title: "BB Lower",
        });
        bbLower.setData(
          indicators
            .filter((d) => d.bb_lower !== null)
            .map((d) => ({ time: d.date as string, value: d.bb_lower! }))
        );
        overlaySeriesRef.current.push(bbLower);
      }
    }

    chart.timeScale().fitContent();
  }, [data, indicators, showSMA, showBollinger]);

  return (
    <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" />
  );
}
