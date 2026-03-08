import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore";
import { useThemeStore } from "../store/themeStore";
import { updateProfile, changePassword, listApiKeys, createApiKey, revokeApiKey } from "../api/auth";
import type { AxiosError } from "axios";
import Card from "../components/common/Card";

function getErrorMessage(err: unknown): string {
  const axErr = err as AxiosError<{ detail: string }>;
  return axErr?.response?.data?.detail ?? "Something went wrong";
}

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const updateUser = useAuthStore((s) => s.updateUser);
  const isDark = useThemeStore((s) => s.isDark);
  const toggle = useThemeStore((s) => s.toggle);

  // Profile form
  const [username, setUsername] = useState(user?.username ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [profileMsg, setProfileMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // Password form
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwMsg, setPwMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [pwLoading, setPwLoading] = useState(false);

  const profileChanged = username !== user?.username || email !== user?.email;

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileMsg(null);
    setProfileLoading(true);
    try {
      const updated = await updateProfile({ username, email });
      updateUser(updated);
      setProfileMsg({ type: "success", text: "Profile updated" });
    } catch (err) {
      setProfileMsg({ type: "error", text: getErrorMessage(err) });
    } finally {
      setProfileLoading(false);
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg(null);

    if (newPw !== confirmPw) {
      setPwMsg({ type: "error", text: "Passwords do not match" });
      return;
    }

    setPwLoading(true);
    try {
      await changePassword({ current_password: currentPw, new_password: newPw });
      setPwMsg({ type: "success", text: "Password updated" });
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      setPwMsg({ type: "error", text: getErrorMessage(err) });
    } finally {
      setPwLoading(false);
    }
  }

  const inputClass =
    "w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent";

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Settings</h1>

      {/* Profile */}
      <Card padding="md" className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Profile</h2>
        <form onSubmit={handleProfileSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>
          {profileMsg && (
            <p className={`text-sm ${profileMsg.type === "success" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
              {profileMsg.text}
            </p>
          )}
          <button
            type="submit"
            disabled={!profileChanged || profileLoading}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            {profileLoading ? "Saving..." : "Save Profile"}
          </button>
        </form>
      </Card>

      {/* Change Password */}
      <Card padding="md" className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Change Password</h2>
        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              Current Password
            </label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              New Password
            </label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              Confirm New Password
            </label>
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
              className={inputClass}
            />
          </div>
          {pwMsg && (
            <p className={`text-sm ${pwMsg.type === "success" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
              {pwMsg.text}
            </p>
          )}
          <button
            type="submit"
            disabled={pwLoading || !currentPw || !newPw || !confirmPw}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            {pwLoading ? "Updating..." : "Update Password"}
          </button>
        </form>
      </Card>

      {/* Appearance */}
      <Card padding="md" className="mb-6">
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
      </Card>

      {/* API Keys */}
      <ApiKeysSection />

      {/* Notifications */}
      <Card padding="md">
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
      </Card>
    </div>
  );
}

function ApiKeysSection() {
  const queryClient = useQueryClient();
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: apiKeys } = useQuery({
    queryKey: ["api-keys"],
    queryFn: listApiKeys,
    staleTime: 30_000,
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreating(true);
    setError(null);
    setCreatedKey(null);
    try {
      const result = await createApiKey(newKeyName.trim());
      setCreatedKey(result.key);
      setNewKeyName("");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    } catch (err) {
      const axErr = err as AxiosError<{ detail: string }>;
      setError(axErr?.response?.data?.detail ?? "Failed to create key");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(keyId: number) {
    try {
      await revokeApiKey(keyId);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    } catch {
      // silently fail
    }
  }

  const inputClass =
    "w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent";

  return (
    <Card padding="md" className="mb-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">API Keys</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Create API keys for programmatic access. Use the <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">X-API-Key</code> header.
      </p>

      {/* Create form */}
      <form onSubmit={handleCreate} className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="Key name (e.g. My Script)"
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
          maxLength={100}
          className={inputClass}
        />
        <button
          type="submit"
          disabled={creating || !newKeyName.trim()}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-lg transition-colors whitespace-nowrap"
        >
          {creating ? "..." : "Create"}
        </button>
      </form>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>}

      {createdKey && (
        <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <p className="text-sm text-green-800 dark:text-green-200 mb-1 font-medium">
            API key created! Copy it now — it won't be shown again.
          </p>
          <code className="text-xs bg-white dark:bg-gray-800 px-2 py-1 rounded block font-mono break-all">
            {createdKey}
          </code>
        </div>
      )}

      {/* Key list */}
      {apiKeys && apiKeys.length > 0 ? (
        <div className="space-y-2">
          {apiKeys.map((k) => (
            <div key={k.id} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700/50">
              <div>
                <span className="text-sm text-gray-900 dark:text-white font-medium">{k.name}</span>
                <span className="text-xs text-gray-400 ml-2 font-mono">{k.key_prefix}...</span>
                {!k.is_active && (
                  <span className="text-xs text-red-500 ml-2">Revoked</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">
                  {k.last_used_at ? `Used ${new Date(k.last_used_at).toLocaleDateString()}` : "Never used"}
                </span>
                {k.is_active && (
                  <button
                    onClick={() => handleRevoke(k.id)}
                    className="text-xs text-red-600 dark:text-red-400 hover:underline"
                  >
                    Revoke
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 dark:text-gray-500">No API keys created yet.</p>
      )}
    </Card>
  );
}
