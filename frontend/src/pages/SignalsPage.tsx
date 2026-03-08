import { useState } from "react";
import type { Signal } from "../types";
import SignalsTab from "../components/signals/SignalsTab";
import AccuracyTab from "../components/signals/AccuracyTab";
import MethodologyTab from "../components/signals/MethodologyTab";
import SignalDetailPanel from "../components/signals/SignalDetailPanel";

type Tab = "signals" | "accuracy" | "methodology";

const TABS: { key: Tab; label: string }[] = [
  { key: "signals", label: "Signals" },
  { key: "accuracy", label: "Accuracy" },
  { key: "methodology", label: "Methodology" },
];

export default function SignalsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("signals");
  const [detailSignal, setDetailSignal] = useState<Signal | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Signals</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-6">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === key
                  ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === "signals" && <SignalsTab onDetailClick={setDetailSignal} />}
      {activeTab === "accuracy" && <AccuracyTab />}
      {activeTab === "methodology" && <MethodologyTab />}

      {/* Signal Detail Panel */}
      {detailSignal && (
        <SignalDetailPanel
          signal={detailSignal}
          onClose={() => setDetailSignal(null)}
        />
      )}
    </div>
  );
}
