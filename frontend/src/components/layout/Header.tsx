import { useAuthStore } from "../../store/authStore";
import { useThemeStore } from "../../store/themeStore";

export default function Header() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const { isDark, toggle } = useThemeStore();

  return (
    <header className="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 flex items-center justify-between">
      <div>
        {/* Search bar placeholder - will be expanded later */}
        <input
          type="text"
          placeholder="Search tickers..."
          className="w-64 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? "Light" : "Dark"}
        </button>

        <span className="text-sm text-gray-600 dark:text-gray-400">
          {user?.username}
        </span>

        <button
          onClick={logout}
          className="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
