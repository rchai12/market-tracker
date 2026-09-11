import WeightsTable from "./WeightsTable";
import MLModelStatusTable from "./MLModelStatusTable";
import Card from "../common/Card";

export default function MethodologyTab() {
  return (
    <div className="space-y-8">
      {/* Scoring Formula */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Composite Signal Scoring
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Each stock is scored using four predictive components, plus gated earnings surprise
          (48h window), options flow when enabled, analyst ratings from LLM-extracted
          articles (30-day window), and the ML ensemble when a model qualifies. RSI and
          trend are used only as market-regime context: they boost or dampen the composite
          rather than adding into it.
        </p>
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 font-mono text-sm text-gray-800 dark:text-gray-200">
          composite = w1 * sentiment_momentum + w2 * sentiment_volume<br />
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w3 * price_momentum + w4 * volume_anomaly<br />
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w5 * earnings + w6 * options + w7 * analyst + w8 * ml<br />
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; × regime_multiplier(RSI, trend)
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">Predictive (always on):</p>
            <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
              <li>Sentiment Momentum: 40%</li>
              <li>Sentiment Volume: 25%</li>
              <li>Price Momentum: 20%</li>
              <li>Volume Anomaly: 15%</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-white">Gated (when active):</p>
            <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
              <li>Earnings Surprise: 10% (within 48h of report)</li>
              <li>Options Flow: 8% (when enabled)</li>
              <li>Analyst Ratings: 7% (30-day LLM-extracted window)</li>
              <li>ML Ensemble: 8% (promoted when model accuracy ≥ 55%, n ≥ 50)</li>
              <li className="text-xs">Other weights scale down so they still sum to 100%</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-white">Regime context (not additive):</p>
            <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
              <li>RSI extreme: dampen 15%</li>
              <li>Trend confirms: boost 15%</li>
              <li>Trend opposes: dampen 15%</li>
            </ul>
          </div>
        </div>
        <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
          <p className="font-medium text-gray-900 dark:text-white mb-1">Strength Thresholds:</p>
          <p>Strong: |score| &gt; 0.6 &nbsp;|&nbsp; Moderate: |score| &gt; 0.35 &nbsp;|&nbsp; Weak: otherwise</p>
        </div>
      </Card>

      {/* Adaptive Weights */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Adaptive Weights by Sector
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          The system learns optimal weights per sector from signal outcome feedback,
          weighting each vote by the size of the subsequent price move. When a
          (sector, regime) pair has enough samples, those regime-specific weights
          take priority. Weights that deviate from defaults are highlighted.
        </p>
        <WeightsTable />
      </Card>

      {/* ML Ensemble */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          ML Signal Ensemble
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          A LightGBM classifier is trained on historical outcomes. When a model meets
          accuracy ≥ 55% and n ≥ 50, its score is promoted into the composite as a gated
          8% component. Otherwise it remains a side-by-side comparison on each signal.
        </p>
        <MLModelStatusTable />
      </Card>
    </div>
  );
}
