import { useEffect, useRef } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import type { IndicatorData } from "../../types";
import { getChartThemeOptions } from "../../utils/chartConfig";

interface RSIChartProps {
  data: IndicatorData[];
  height?: number;
}

export default function RSIChart({ data, height = 150 }: RSIChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const isDark = document.documentElement.classList.contains("dark");

    const chart = createChart(chartContainerRef.current, {
      ...getChartThemeOptions(isDark),
      width: chartContainerRef.current.clientWidth,
      height,
      rightPriceScale: {
        autoScale: false,
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
    });

    const rsiSeries = chart.addLineSeries({
      color: "#eab308",
      lineWidth: 2,
      title: "RSI",
    });

    const rsiData = data
      .filter((d) => d.rsi !== null)
      .map((d) => ({ time: d.date as string, value: d.rsi! }));

    rsiSeries.setData(rsiData);

    // Overbought/oversold reference lines
    rsiSeries.createPriceLine({
      price: 70,
      color: "#ef4444",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "",
    });
    rsiSeries.createPriceLine({
      price: 30,
      color: "#22c55e",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "",
    });
    rsiSeries.createPriceLine({
      price: 50,
      color: isDark ? "#4b5563" : "#d1d5db",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: false,
      title: "",
    });

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
