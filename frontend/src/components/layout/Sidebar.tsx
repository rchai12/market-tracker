import { NavLink, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listSectors } from "../../api/stocks";

const navItems = [
  { to: "/", label: "Dashboard", icon: "grid" },
  { to: "/signals", label: "Signals", icon: "zap" },
  { to: "/sentiment", label: "Sentiment", icon: "activity" },
  { to: "/watchlist", label: "Watchlist", icon: "star" },
  { to: "/alerts", label: "Alerts", icon: "bell" },
  { to: "/settings", label: "Settings", icon: "settings" },
];

export default function Sidebar() {
  const [searchParams] = useSearchParams();
  const activeSector = searchParams.get("sector");

  const { data: sectors } = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
    staleTime: 5 * 60 * 1000,
  });

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
        <p className="text-xs text-gray-500 dark:text-gray-400 px-3 mb-2">
          Sectors
        </p>
        <div className="space-y-1">
          <NavLink
            to="/signals"
            end
            className={`block px-3 py-1.5 text-sm rounded-lg transition-colors ${
              !activeSector
                ? "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
            }`}
          >
            All Sectors
          </NavLink>
          {sectors?.map((sector) => (
            <NavLink
              key={sector}
              to={`/signals?sector=${encodeURIComponent(sector)}`}
              className={`block px-3 py-1.5 text-sm rounded-lg transition-colors ${
                activeSector === sector
                  ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
              }`}
            >
              {sector}
            </NavLink>
          ))}
        </div>
      </div>
    </aside>
  );
}
