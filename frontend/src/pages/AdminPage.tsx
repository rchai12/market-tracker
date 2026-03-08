import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  triggerScrape,
  triggerSeedHistory,
  triggerMaintenance,
  triggerOutcomeEval,
  triggerWeightCompute,
  getDbStats,
} from "../api/admin";
import type { TaskResponse } from "../api/admin";
import type { AxiosError } from "axios";
import Card from "../components/common/Card";

function TaskButton({
  label,
  onTrigger,
}: {
  label: string;
  onTrigger: () => Promise<TaskResponse>;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await onTrigger();
      setResult(res.task_id);
    } catch (err) {
      const axErr = err as AxiosError<{ detail: string }>;
      setError(axErr?.response?.data?.detail ?? "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{label}</h3>
        <button
          onClick={handleClick}
          disabled={loading}
          className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-lg transition-colors"
        >
          {loading ? "Queuing..." : "Run"}
        </button>
      </div>
      {result && (
        <p className="text-xs text-green-600 dark:text-green-400">
          Queued: <span className="font-mono">{result.slice(0, 12)}...</span>
        </p>
      )}
      {error && (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </Card>
  );
}

export default function AdminPage() {
  const [seedPeriod, setSeedPeriod] = useState("max");

  const { data: dbStats, isLoading: statsLoading } = useQuery({
    queryKey: ["admin-db-stats"],
    queryFn: getDbStats,
    staleTime: 60_000,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Admin</h1>

      {/* Task Triggers */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Task Triggers</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <TaskButton label="Scrape Now" onTrigger={triggerScrape} />
          <Card>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Seed History</h3>
              <div className="flex items-center gap-2">
                <select
                  value={seedPeriod}
                  onChange={(e) => setSeedPeriod(e.target.value)}
                  className="text-xs border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white px-1.5 py-1"
                >
                  <option value="1y">1 year</option>
                  <option value="2y">2 years</option>
                  <option value="5y">5 years</option>
                  <option value="10y">10 years</option>
                  <option value="max">Max</option>
                </select>
                <SeedButton period={seedPeriod} />
              </div>
            </div>
          </Card>
          <TaskButton label="Maintenance" onTrigger={triggerMaintenance} />
          <TaskButton label="Evaluate Outcomes" onTrigger={triggerOutcomeEval} />
          <TaskButton label="Compute Weights" onTrigger={triggerWeightCompute} />
        </div>
      </section>

      {/* Database Stats */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Database Stats</h2>
        <Card padding="none" className="overflow-hidden">
          {statsLoading ? (
            <div className="p-6 text-sm text-gray-500 dark:text-gray-400">Loading...</div>
          ) : dbStats ? (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Table</th>
                    <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Rows</th>
                    <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Size</th>
                  </tr>
                </thead>
                <tbody>
                  {dbStats.tables.map((t) => (
                    <tr key={t.table} className="border-b border-gray-100 dark:border-gray-700/50">
                      <td className="px-4 py-2 text-gray-900 dark:text-white font-mono text-xs">{t.table}</td>
                      <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">
                        {t.estimated_rows.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">{t.total_size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-between text-sm font-medium">
                <span className="text-gray-900 dark:text-white">Total</span>
                <span className="text-gray-900 dark:text-white">{dbStats.total_size}</span>
              </div>
            </>
          ) : (
            <div className="p-6 text-sm text-gray-500 dark:text-gray-400">Failed to load stats</div>
          )}
        </Card>
      </section>
    </div>
  );
}

function SeedButton({ period }: { period: string }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setResult(null);
    try {
      const res = await triggerSeedHistory(period);
      setResult(res.task_id);
    } catch {
      setResult("error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={loading}
        className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-lg transition-colors"
      >
        {loading ? "..." : "Run"}
      </button>
      {result && result !== "error" && (
        <p className="text-xs text-green-600 dark:text-green-400 mt-1">
          Queued
        </p>
      )}
    </div>
  );
}
