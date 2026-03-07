import { useEffect, useRef } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import type { EquityPoint } from "../../types";
import { getChartThemeOptions } from "../../utils/chartConfig";

interface EquityCurveChartProps {
  data: EquityPoint[];
  startingCapital: number;
  height?: number;
}

export default function EquityCurveChart({
  data,
  startingCapital,
  height = 300,
}: EquityCurveChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const isDark = document.documentElement.classList.contains("dark");

    const chart = createChart(chartContainerRef.current, {
      ...getChartThemeOptions(isDark),
      width: chartContainerRef.current.clientWidth,
      height,
    });

    // Equity line
    const equitySeries = chart.addLineSeries({
      color: "#22c55e",
      lineWidth: 2,
      title: "Equity",
    });

    equitySeries.setData(
      data.map((d) => ({ time: d.date as string, value: d.equity }))
    );

    // Starting capital baseline
    equitySeries.createPriceLine({
      price: startingCapital,
      color: isDark ? "#6b7280" : "#9ca3af",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
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
  }, [data, startingCapital, height]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full rounded-lg overflow-hidden"
    />
  );
}
