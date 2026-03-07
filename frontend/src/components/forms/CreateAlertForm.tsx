import { useState } from "react";

export interface CreateAlertFormData {
  min_strength: string;
  channel: string;
  direction_filter?: string[];
}

interface CreateAlertFormProps {
  onSubmit: (data: CreateAlertFormData) => void;
  isPending: boolean;
  onCancel: () => void;
}

export default function CreateAlertForm({ onSubmit, isPending, onCancel }: CreateAlertFormProps) {
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
