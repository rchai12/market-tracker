import { useEffect, useRef } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import type { IndicatorData } from "../../types";
import { getChartThemeOptions } from "../../utils/chartConfig";

interface MACDChartProps {
  data: IndicatorData[];
  height?: number;
}

export default function MACDChart({ data, height = 180 }: MACDChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const isDark = document.documentElement.classList.contains("dark");

    const chart = createChart(chartContainerRef.current, {
      ...getChartThemeOptions(isDark),
      width: chartContainerRef.current.clientWidth,
      height,
    });

    // MACD line
    const macdSeries = chart.addLineSeries({
      color: "#3b82f6",
      lineWidth: 2,
      title: "MACD",
    });

    // Signal line
    const signalSeries = chart.addLineSeries({
      color: "#f97316",
      lineWidth: 2,
      title: "Signal",
    });

    // Histogram
    const histogramSeries = chart.addHistogramSeries({
      title: "Histogram",
    });

    const macdData = data
      .filter((d) => d.macd_line !== null)
      .map((d) => ({ time: d.date as string, value: d.macd_line! }));

    const signalData = data
      .filter((d) => d.macd_signal !== null)
      .map((d) => ({ time: d.date as string, value: d.macd_signal! }));

    const histData = data
      .filter((d) => d.macd_histogram !== null)
      .map((d) => ({
        time: d.date as string,
        value: d.macd_histogram!,
        color: d.macd_histogram! >= 0 ? "#22c55e" : "#ef4444",
      }));

    macdSeries.setData(macdData);
    signalSeries.setData(signalData);
    histogramSeries.setData(histData);

    chartRef.current = chart;
    chart.timeScale().fitContent();

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
  }, [data, height]);

  return (
    <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" />
  );
}
