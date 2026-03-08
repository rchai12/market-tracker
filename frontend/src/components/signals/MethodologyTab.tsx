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
          Each stock is scored using 6 components that combine sentiment analysis with technical indicators.
          The composite score determines signal direction and strength.
        </p>
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 font-mono text-sm text-gray-800 dark:text-gray-200">
          composite = w1 * sentiment_momentum + w2 * sentiment_volume<br />
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w3 * price_momentum + w4 * volume_anomaly<br />
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w5 * rsi + w6 * trend
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">Default Weights:</p>
            <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
              <li>Sentiment Momentum: 30%</li>
              <li>Sentiment Volume: 20%</li>
              <li>Price Momentum: 15%</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-white">&nbsp;</p>
            <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
              <li>Volume Anomaly: 10%</li>
              <li>RSI: 15%</li>
              <li>Trend: 10%</li>
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
          The system learns optimal weights per sector from signal outcome feedback.
          Weights that deviate from defaults are highlighted.
        </p>
        <WeightsTable />
      </Card>

      {/* ML Ensemble */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          ML Signal Ensemble
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          A LightGBM classifier runs alongside the rule-based scoring. It learns from
          historical signal outcomes which component score patterns lead to correct
          predictions. Both scores are computed for every signal, enabling A/B comparison.
        </p>
        <MLModelStatusTable />
      </Card>
    </div>
  );
}
