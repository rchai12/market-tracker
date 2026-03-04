import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard", icon: "grid" },
  { to: "/signals", label: "Signals", icon: "zap" },
  { to: "/sentiment", label: "Sentiment", icon: "activity" },
  { to: "/watchlist", label: "Watchlist", icon: "star" },
  { to: "/alerts", label: "Alerts", icon: "bell" },
  { to: "/settings", label: "Settings", icon: "settings" },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 min-h-screen p-4">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
          Stock Predictor
        </h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Sentiment-driven signals
        </p>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                  : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-8 pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 px-3">
          Sectors
        </p>
        <div className="mt-2 space-y-1">
          <span className="block px-3 py-1 text-sm text-gray-600 dark:text-gray-400">
            Energy
          </span>
          <span className="block px-3 py-1 text-sm text-gray-600 dark:text-gray-400">
            Financials
          </span>
        </div>
      </div>
    </aside>
  );
}
