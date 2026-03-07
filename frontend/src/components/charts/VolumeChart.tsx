import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import type { MarketDataDaily } from "../../types";
import { getChartThemeOptions } from "../../utils/chartConfig";

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
    const themeOptions = getChartThemeOptions(isDark);

    const chart = createChart(chartContainerRef.current, {
      ...themeOptions,
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? "#374151" : "#e5e7eb" },
      },
      width: chartContainerRef.current.clientWidth,
      height,
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
