import { useEffect, useRef } from "react";
import { createChart, type IChartApi, ColorType } from "lightweight-charts";
import type { MarketDataDaily } from "../../types";

interface SparklineChartProps {
  data: MarketDataDaily[];
  height?: number;
}

export default function SparklineChart({ data, height = 40 }: SparklineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || data.length < 2) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "transparent",
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
      crosshair: { mode: 0 },
    });

    const isUp = data[data.length - 1].close >= data[0].close;
    const lineColor = isUp ? "#22c55e" : "#ef4444";

    const series = chart.addLineSeries({
      color: lineColor,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    series.setData(data.map((d) => ({ time: d.date as string, value: d.close })));
    chart.timeScale().fitContent();
    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height]);

  return <div ref={containerRef} className="w-full" />;
}
