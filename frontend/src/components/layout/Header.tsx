import { useAuthStore } from "../../store/authStore";
import { useThemeStore } from "../../store/themeStore";
import { useSidebarStore } from "../../store/sidebarStore";
import SearchBar from "./SearchBar";

export default function Header() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const { isDark, toggle } = useThemeStore();
  const toggleSidebar = useSidebarStore((s) => s.toggle);

  return (
    <header className="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 md:px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={toggleSidebar}
          className="md:hidden p-1.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Toggle sidebar"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <SearchBar />
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggle}
          className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? "Light" : "Dark"}
        </button>

        <span className="text-sm text-gray-600 dark:text-gray-400 hidden sm:inline">
          {user?.username}
        </span>

        <button
          type="button"
          onClick={logout}
          className="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
          aria-label="Log out"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
