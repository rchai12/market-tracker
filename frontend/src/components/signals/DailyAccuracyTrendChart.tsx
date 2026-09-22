import type { DailyViewAccuracyTrendBucket } from "../../types";

interface DailyAccuracyTrendChartProps {
  buckets: DailyViewAccuracyTrendBucket[];
}

function formatWeek(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function DailyAccuracyTrendChart({ buckets }: DailyAccuracyTrendChartProps) {
  if (buckets.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
        No weekly accuracy yet. Points appear after daily views are evaluated.
      </p>
    );
  }

  const width = 640;
  const height = 180;
  const pad = { l: 36, r: 12, t: 12, b: 28 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const ys = buckets.map((b) => b.accuracy_pct);
  const minY = Math.min(40, ...ys);
  const maxY = Math.max(70, ...ys);
  const span = Math.max(maxY - minY, 1);

  const xAt = (i: number) =>
    pad.l + (buckets.length === 1 ? innerW / 2 : (i / (buckets.length - 1)) * innerW);
  const yAt = (v: number) => pad.t + innerH - ((v - minY) / span) * innerH;
  const y50 = yAt(50);
  const points = buckets.map((b, i) => `${xAt(i).toFixed(1)},${yAt(b.accuracy_pct).toFixed(1)}`).join(" ");

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48 text-gray-900 dark:text-white">
        <line x1={pad.l} x2={width - pad.r} y1={y50} y2={y50} stroke="currentColor" strokeOpacity="0.25" strokeDasharray="4 4" />
        <polyline fill="none" stroke="#10b981" strokeWidth="2" points={points} />
        {buckets.map((b, i) => (
          <circle key={b.week_start} cx={xAt(i)} cy={yAt(b.accuracy_pct)} r="3.5" fill="#10b981" />
        ))}
        {buckets.map((b, i) => (
          <text
            key={`${b.week_start}-label`}
            x={xAt(i)}
            y={height - 8}
            textAnchor="middle"
            className="fill-gray-500 dark:fill-gray-400"
            fontSize="10"
          >
            {formatWeek(b.week_start)}
          </text>
        ))}
        <text x={4} y={yAt(maxY) + 4} fontSize="10" className="fill-gray-500 dark:fill-gray-400">
          {maxY.toFixed(0)}%
        </text>
        <text x={4} y={y50 + 4} fontSize="10" className="fill-gray-500 dark:fill-gray-400">
          50%
        </text>
      </svg>
    </div>
  );
}
