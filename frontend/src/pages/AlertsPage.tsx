import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAlertConfigs,
  createAlertConfig,
  deleteAlertConfig,
  updateAlertConfig,
  getAlertHistory,
  sendTestAlert,
} from "../api/alerts";

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ["alert-configs"],
    queryFn: getAlertConfigs,
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["alert-history"],
    queryFn: () => getAlertHistory(1, 20),
  });

  const createMutation = useMutation({
    mutationFn: createAlertConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-configs"] });
      setShowCreate(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAlertConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alert-configs"] }),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      updateAlertConfig(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alert-configs"] }),
  });

  const testMutation = useMutation({
    mutationFn: (channel: string) => sendTestAlert(channel),
    onSuccess: (data) => setTestResult(data.message),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Alerts</h1>
        <div className="flex gap-2">
          <button
            onClick={() => testMutation.mutate("discord")}
            disabled={testMutation.isPending}
            className="px-3 py-2 text-sm rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400"
          >
            Test Discord
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            New Alert Config
          </button>
        </div>
      </div>

      {testResult && (
        <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3 mb-4 text-sm text-gray-700 dark:text-gray-300">
          {testResult}
          <button onClick={() => setTestResult(null)} className="ml-2 text-gray-400 hover:text-gray-600">x</button>
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">New Alert Configuration</h2>
          <CreateAlertForm
            onSubmit={(data) => createMutation.mutate(data)}
            isPending={createMutation.isPending}
            onCancel={() => setShowCreate(false)}
          />
        </div>
      )}

      {/* Configs */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Alert Configurations</h2>
        {configsLoading ? (
          <p className="text-gray-500 dark:text-gray-400">Loading...</p>
        ) : configs && configs.length > 0 ? (
          <div className="space-y-3">
            {configs.map((config) => (
              <div
                key={config.id}
                className={`border rounded-lg p-4 ${config.is_active ? "border-gray-200 dark:border-gray-700" : "border-gray-100 dark:border-gray-800 opacity-60"}`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {config.ticker || "All Stocks"}
                    </span>
                    <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
                      {config.min_strength}+ | {config.channel}
                    </span>
                    {config.direction_filter && (
                      <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
                        ({config.direction_filter.join(", ")})
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => toggleMutation.mutate({ id: config.id, is_active: !config.is_active })}
                      className={`px-3 py-1 text-xs rounded-lg ${config.is_active ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"}`}
                    >
                      {config.is_active ? "Active" : "Paused"}
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(config.id)}
                      className="px-3 py-1 text-xs rounded-lg bg-red-50 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            No alert configs yet. Create one to receive notifications when signals trigger.
          </p>
        )}
      </div>

      {/* History */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Alert History</h2>
        {historyLoading ? (
          <p className="text-gray-500 dark:text-gray-400">Loading...</p>
        ) : history && history.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Ticker</th>
                  <th className="text-center py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Signal</th>
                  <th className="text-center py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Channel</th>
                  <th className="text-center py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                  <th className="text-right py-2 px-3 text-gray-500 dark:text-gray-400 font-medium">Sent</th>
                </tr>
              </thead>
              <tbody>
                {history.data.map((log) => (
                  <tr key={log.id} className="border-b border-gray-100 dark:border-gray-700/50">
                    <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{log.ticker || "—"}</td>
                    <td className="py-2 px-3 text-center">
                      <span className={`text-sm ${log.direction === "bullish" ? "text-green-600 dark:text-green-400" : log.direction === "bearish" ? "text-red-600 dark:text-red-400" : "text-gray-500"}`}>
                        {log.direction} ({log.strength})
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center text-gray-600 dark:text-gray-300">{log.channel}</td>
                    <td className="py-2 px-3 text-center">
                      <span className={log.success ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                        {log.success ? "Sent" : "Failed"}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-gray-500 dark:text-gray-400 text-xs">
                      {new Date(log.sent_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            No alerts sent yet. Alerts will appear here when signals match your configurations.
          </p>
        )}
      </div>
    </div>
  );
}

function CreateAlertForm({
  onSubmit,
  isPending,
  onCancel,
}: {
  onSubmit: (data: { min_strength: string; channel: string; direction_filter?: string[] }) => void;
  isPending: boolean;
  onCancel: () => void;
}) {
  const [minStrength, setMinStrength] = useState("moderate");
  const [channel, setChannel] = useState("both");
  const [dirFilter, setDirFilter] = useState<string[]>([]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      min_strength: minStrength,
      channel,
      direction_filter: dirFilter.length > 0 ? dirFilter : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Min Strength</label>
          <select
            value={minStrength}
            onChange={(e) => setMinStrength(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
          >
            <option value="weak">Weak+</option>
            <option value="moderate">Moderate+</option>
            <option value="strong">Strong only</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Channel</label>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
          >
            <option value="both">Both</option>
            <option value="discord">Discord</option>
            <option value="email">Email</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Direction</label>
          <div className="flex gap-2 mt-2">
            {["bullish", "bearish"].map((dir) => (
              <label key={dir} className="flex items-center gap-1 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={dirFilter.includes(dir)}
                  onChange={(e) => {
                    if (e.target.checked) setDirFilter([...dirFilter, dir]);
                    else setDirFilter(dirFilter.filter((d) => d !== dir));
                  }}
                  className="rounded"
                />
                {dir}
              </label>
            ))}
          </div>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isPending}
          className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isPending ? "Creating..." : "Create"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
