import { useAuthStore } from "../store/authStore";

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">
            Stock Predictor
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {user?.username}
            </span>
            <button
              onClick={logout}
              className="text-sm text-red-600 hover:text-red-800"
            >
              Logout
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Latest Signals
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              Signal data will appear here once the pipeline is running.
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Sentiment Overview
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              Sector sentiment heatmap coming in Phase 7.
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Top Movers
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              Top bullish and bearish stocks will appear here.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
