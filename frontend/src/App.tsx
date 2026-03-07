import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import AppLayout from "./components/layout/AppLayout";
import LoginPage from "./pages/LoginPage";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const SignalsPage = lazy(() => import("./pages/SignalsPage"));
const SentimentPage = lazy(() => import("./pages/SentimentPage"));
const WatchlistPage = lazy(() => import("./pages/WatchlistPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const BacktestPage = lazy(() => import("./pages/BacktestPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const StockDetailPage = lazy(() => import("./pages/StockDetailPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-gray-500 dark:text-gray-400 text-sm">Loading...</div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((state) => state.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((state) => state.user);
  if (!user?.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route
          path="/"
          element={
            <Suspense fallback={<PageFallback />}>
              <DashboardPage />
            </Suspense>
          }
        />
        <Route
          path="/stocks/:ticker"
          element={
            <Suspense fallback={<PageFallback />}>
              <StockDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/signals"
          element={
            <Suspense fallback={<PageFallback />}>
              <SignalsPage />
            </Suspense>
          }
        />
        <Route
          path="/backtest"
          element={
            <Suspense fallback={<PageFallback />}>
              <BacktestPage />
            </Suspense>
          }
        />
        <Route
          path="/sentiment"
          element={
            <Suspense fallback={<PageFallback />}>
              <SentimentPage />
            </Suspense>
          }
        />
        <Route
          path="/watchlist"
          element={
            <Suspense fallback={<PageFallback />}>
              <WatchlistPage />
            </Suspense>
          }
        />
        <Route
          path="/alerts"
          element={
            <Suspense fallback={<PageFallback />}>
              <AlertsPage />
            </Suspense>
          }
        />
        <Route
          path="/settings"
          element={
            <Suspense fallback={<PageFallback />}>
              <SettingsPage />
            </Suspense>
          }
        />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <Suspense fallback={<PageFallback />}>
                <AdminPage />
              </Suspense>
            </AdminRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
