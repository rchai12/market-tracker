import { useEffect, useRef } from "react";
import { createChart, type IChartApi, ColorType } from "lightweight-charts";
import type { SentimentTimePoint } from "../../types";

interface SentimentChartProps {
  data: SentimentTimePoint[];
  height?: number;
}

export default function SentimentChart({ data, height = 200 }: SentimentChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const isDark = document.documentElement.classList.contains("dark");

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: isDark ? "#1f2937" : "#ffffff" },
        textColor: isDark ? "#9ca3af" : "#374151",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? "#374151" : "#e5e7eb" },
      },
      width: chartContainerRef.current.clientWidth,
      height,
      timeScale: {
        borderColor: isDark ? "#4b5563" : "#d1d5db",
      },
      rightPriceScale: {
        borderColor: isDark ? "#4b5563" : "#d1d5db",
      },
    });

    const positiveSeries = chart.addLineSeries({
      color: "#22c55e",
      lineWidth: 2,
      title: "Positive",
    });

    const negativeSeries = chart.addLineSeries({
      color: "#ef4444",
      lineWidth: 2,
      title: "Negative",
    });

    const neutralSeries = chart.addLineSeries({
      color: "#6b7280",
      lineWidth: 1,
      lineStyle: 2,
      title: "Neutral",
    });

    const posData = data.map((d) => ({ time: d.date as string, value: d.avg_positive }));
    const negData = data.map((d) => ({ time: d.date as string, value: d.avg_negative }));
    const neuData = data.map((d) => ({ time: d.date as string, value: d.avg_neutral }));

    positiveSeries.setData(posData);
    negativeSeries.setData(negData);
    neutralSeries.setData(neuData);
    chart.timeScale().fitContent();

    chartRef.current = chart;

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
