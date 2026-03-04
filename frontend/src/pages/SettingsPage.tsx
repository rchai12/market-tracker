import { Link } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { useThemeStore } from "../store/themeStore";

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const isDark = useThemeStore((s) => s.isDark);
  const toggle = useThemeStore((s) => s.toggle);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Settings</h1>

      {/* Profile */}
      <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Profile</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400">
              Username
            </label>
            <p className="text-gray-900 dark:text-white mt-1">{user?.username ?? "—"}</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400">
              Email
            </label>
            <p className="text-gray-900 dark:text-white mt-1">{user?.email ?? "—"}</p>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">
          Profile editing will be available in a future update.
        </p>
      </section>

      {/* Appearance */}
      <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Appearance</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-900 dark:text-white">Dark Mode</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Toggle between light and dark themes
            </p>
          </div>
          <button
            onClick={toggle}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isDark ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                isDark ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </section>

      {/* Notifications */}
      <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Notifications</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-900 dark:text-white">Discord Webhook</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Configured via environment variable on the server
              </p>
            </div>
            <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-1 rounded">
              Server-managed
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-900 dark:text-white">Email Alerts</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Sent to your registered email address
              </p>
            </div>
            <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-1 rounded">
              {user?.email ?? "—"}
            </span>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">
          Manage your alert configurations on the{" "}
          <Link to="/alerts" className="text-blue-600 dark:text-blue-400 hover:underline">
            Alerts page
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
