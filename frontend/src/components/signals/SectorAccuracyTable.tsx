import type { DailyViewRegimeAccuracy, DailyViewSectorAccuracy } from "../../types";

const MIN_GROUP_COUNT = 5;

interface SectorAccuracyTableProps {
  sectors: DailyViewSectorAccuracy[];
}

function formatAlpha(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function GroupTable({
  rows,
  labelHeader,
}: {
  rows: { name: string; count: number; accuracy_pct: number; avg_excess_return: number }[];
  labelHeader: string;
}) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
        Need at least {MIN_GROUP_COUNT} evaluated views per row to show this breakdown.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
            <th className="text-left py-2 font-medium">{labelHeader}</th>
            <th className="text-right py-2 font-medium">Views</th>
            <th className="text-right py-2 font-medium">Accuracy</th>
            <th className="text-right py-2 font-medium">Avg α</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-gray-100 dark:border-gray-700/50 last:border-b-0">
              <td className="py-2 text-gray-900 dark:text-white">{row.name}</td>
              <td className="py-2 text-right text-gray-700 dark:text-gray-300">{row.count}</td>
              <td className={`py-2 text-right font-mono ${row.accuracy_pct >= 50 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                {row.accuracy_pct.toFixed(1)}%
              </td>
              <td className="py-2 text-right font-mono text-gray-700 dark:text-gray-300">
                {formatAlpha(row.avg_excess_return)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function visibleAccuracyRows<T extends { count: number }>(rows: T[], minCount = MIN_GROUP_COUNT): T[] {
  return rows.filter((row) => row.count >= minCount);
}

export default function SectorAccuracyTable({ sectors }: SectorAccuracyTableProps) {
  const rows = visibleAccuracyRows(sectors).map((s) => ({
    name: s.sector,
    count: s.count,
    accuracy_pct: s.accuracy_pct,
    avg_excess_return: s.avg_excess_return,
  }));
  return <GroupTable rows={rows} labelHeader="Sector" />;
}

export function RegimeAccuracyTable({ regimes }: { regimes: DailyViewRegimeAccuracy[] }) {
  const rows = visibleAccuracyRows(regimes).map((r) => ({
    name: r.regime.replace(/_/g, " "),
    count: r.count,
    accuracy_pct: r.accuracy_pct,
    avg_excess_return: r.avg_excess_return,
  }));
  return <GroupTable rows={rows} labelHeader="Regime" />;
}
