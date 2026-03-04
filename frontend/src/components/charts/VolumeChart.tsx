import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";
import type { MarketDataDaily } from "../../types";

interface VolumeChartProps {
  data: MarketDataDaily[];
  height?: number;
}

export default function VolumeChart({ data, height = 150 }: VolumeChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

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

    const volumeSeries = chart.addHistogramSeries({
      color: "#6366f1",
      priceFormat: { type: "volume" },
    });

    chartRef.current = chart;
    seriesRef.current = volumeSeries;

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

    const chartData = data.map((d, i) => ({
      time: d.date as string,
      value: d.volume ?? 0,
      color: i > 0 && d.close >= data[i - 1]!.close ? "#22c55e80" : "#ef444480",
    }));

    seriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" />
  );
}
