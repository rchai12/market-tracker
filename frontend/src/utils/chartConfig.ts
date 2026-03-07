import { ColorType, type DeepPartial, type ChartOptions } from "lightweight-charts";

export function getChartThemeOptions(isDark: boolean): DeepPartial<ChartOptions> {
  return {
    layout: {
      background: { type: ColorType.Solid, color: isDark ? "#1f2937" : "#ffffff" },
      textColor: isDark ? "#9ca3af" : "#374151",
    },
    grid: {
      vertLines: { color: isDark ? "#374151" : "#e5e7eb" },
      horzLines: { color: isDark ? "#374151" : "#e5e7eb" },
    },
    timeScale: {
      borderColor: isDark ? "#4b5563" : "#d1d5db",
    },
    rightPriceScale: {
      borderColor: isDark ? "#4b5563" : "#d1d5db",
    },
  };
}
