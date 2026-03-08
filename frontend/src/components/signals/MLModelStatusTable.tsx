import { useQuery } from "@tanstack/react-query";
import { getMLModelStatus } from "../../api/admin";

function accuracyColor(val: number | null): string {
  if (val == null) return "text-gray-500 dark:text-gray-400";
  if (val >= 55) return "text-emerald-600 dark:text-emerald-400";
  if (val >= 50) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function ImportanceBars({ importances }: { importances: Record<string, number> }) {
  const entries = Object.entries(importances).sort((a, b) => b[1] - a[1]);
  return (
    <div className="flex gap-0.5">
      {entries.map(([name, value]) => (
        <div
          key={name}
          className="h-3 bg-purple-500 dark:bg-purple-400 rounded-sm"
          style={{ width: `${Math.max(value * 100, 2)}%` }}
          title={`${name}: ${(value * 100).toFixed(1)}%`}
        />
      ))}
    </div>
  );
}

export default function MLModelStatusTable() {
  const { data: models, isLoading, isError } = useQuery({
    queryKey: ["ml-model-status"],
    queryFn: getMLModelStatus,
    staleTime: 60_000,
  });

  if (isLoading) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Loading ML models...</p>;
  }

  if (isError) {
    return <p className="text-sm text-red-500 dark:text-red-400">Failed to load ML models</p>;
  }

  if (!models || models.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400">
        No ML models trained yet. Enable ML_ENSEMBLE_ENABLED and trigger training.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            <th className="text-left px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Sector</th>
            <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">v</th>
            <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Samples</th>
            <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Accuracy</th>
            <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">F1</th>
            <th className="px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Importances</th>
            <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Trained</th>
          </tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr
              key={m.sector_name ?? "global"}
              className={`border-b border-gray-100 dark:border-gray-700/50 ${
                m.sector_name == null ? "bg-blue-50/50 dark:bg-blue-900/10" : ""
              }`}
            >
              <td className="px-3 py-2 text-gray-900 dark:text-white font-medium">
                {m.sector_name ?? "Global (fallback)"}
              </td>
              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{m.model_version}</td>
              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                {m.training_samples.toLocaleString()}
              </td>
              <td className={`px-3 py-2 text-right font-medium ${accuracyColor(m.validation_accuracy)}`}>
                {m.validation_accuracy != null ? `${m.validation_accuracy.toFixed(1)}%` : "-"}
              </td>
              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                {m.validation_f1 != null ? m.validation_f1.toFixed(3) : "-"}
              </td>
              <td className="px-3 py-2 w-32">
                {m.feature_importances ? (
                  <ImportanceBars importances={m.feature_importances} />
                ) : (
                  <span className="text-gray-400">-</span>
                )}
              </td>
              <td className="px-3 py-2 text-right text-gray-500 dark:text-gray-400 text-xs">
                {m.trained_at
                  ? new Date(m.trained_at).toLocaleDateString()
                  : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
