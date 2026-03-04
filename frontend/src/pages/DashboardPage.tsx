export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Dashboard</h1>
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
    </div>
  );
}
