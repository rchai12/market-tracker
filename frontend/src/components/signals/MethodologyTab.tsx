import { useQuery } from "@tanstack/react-query";
import WeightsTable from "./WeightsTable";
import MLModelStatusTable from "./MLModelStatusTable";
import Card from "../common/Card";
import LoadingSkeleton from "../common/LoadingSkeleton";
import ErrorRetry from "../common/ErrorRetry";
import { getSignalWeights } from "../../api/signals";
import type { SignalFormulaDefaults, SignalWeightsPayload } from "../../types";

function formatWeightPct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatAccuracyGate(value: number): string {
  const pct = value <= 1 ? value * 100 : value;
  return `${Math.round(pct)}%`;
}

function FormulaCopy({ defaults }: { defaults: SignalFormulaDefaults }) {
  const regimePct = formatWeightPct(defaults.regime_adjustment);
  const mlAccuracy = formatAccuracyGate(defaults.ml_min_accuracy);
  return (
    <>
      <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 font-mono text-sm text-gray-800 dark:text-gray-200">
        composite = w1 * sentiment_momentum + w2 * sentiment_volume<br />
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w3 * price_momentum + w4 * volume_anomaly<br />
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; + w5 * earnings + w6 * options + w7 * analyst + w8 * ml + w9 * insider<br />
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; × regime_multiplier(RSI, trend)
      </div>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
        <div>
          <p className="font-medium text-gray-900 dark:text-white">Predictive (always on):</p>
          <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
            <li>Sentiment Momentum: {formatWeightPct(defaults.sentiment_momentum)}</li>
            <li>Sentiment Volume: {formatWeightPct(defaults.sentiment_volume)}</li>
            <li>Price Momentum: {formatWeightPct(defaults.price_momentum)}</li>
            <li>Volume Anomaly: {formatWeightPct(defaults.volume_anomaly)}</li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-gray-900 dark:text-white">Gated (when active):</p>
          <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
            <li>Earnings Surprise: {formatWeightPct(defaults.earnings)} (within 48h of report)</li>
            <li>Options Flow: {formatWeightPct(defaults.options)} (when enabled)</li>
            <li>Analyst Ratings: {formatWeightPct(defaults.analyst)} (30-day LLM-extracted window)</li>
            <li>
              ML Ensemble: {formatWeightPct(defaults.ml)} (promoted when model accuracy ≥ {mlAccuracy}, n ≥{" "}
              {defaults.ml_min_samples})
            </li>
            <li>
              Insider Trading: {formatWeightPct(defaults.insider)} (30-day Form 4 window, role-weighted, sells
              discounted 60%)
            </li>
            <li className="text-xs">Other weights scale down so they still sum to 100%</li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-gray-900 dark:text-white">Regime context (not additive):</p>
          <ul className="mt-1 space-y-1 text-gray-600 dark:text-gray-400">
            <li>RSI extreme: dampen {regimePct}</li>
            <li>Trend confirms: boost {regimePct}</li>
            <li>Trend opposes: dampen {regimePct}</li>
          </ul>
        </div>
      </div>
      <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
        <p className="font-medium text-gray-900 dark:text-white mb-1">Strength Thresholds:</p>
        <p>
          Strong: |score| &gt; {defaults.strong_threshold} &nbsp;|&nbsp; Moderate: |score| &gt;{" "}
          {defaults.moderate_threshold} &nbsp;|&nbsp; Weak: otherwise
        </p>
      </div>
    </>
  );
}

export default function MethodologyTab() {
  const { data, isLoading, error, refetch } = useQuery<SignalWeightsPayload>({
    queryKey: ["signal-weights"],
    queryFn: getSignalWeights,
  });

  return (
    <div className="space-y-8">
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Composite Signal Scoring
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Each stock is scored using four predictive components, plus gated earnings surprise
          (48h window), options flow when enabled, analyst ratings from LLM-extracted
          articles (30-day window), the ML ensemble when a model qualifies, and insider
          Form 4 activity (30-day window). RSI and trend are used only as market-regime
          context: they boost or dampen the composite rather than adding into it.
        </p>
        {isLoading && <LoadingSkeleton variant="row" count={4} />}
        {error && <ErrorRetry message="Failed to load scoring formula" onRetry={refetch} />}
        {data?.defaults && <FormulaCopy defaults={data.defaults} />}
      </Card>

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

      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          ML Signal Ensemble
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          A LightGBM classifier is trained on historical outcomes. When a model meets
          the accuracy and sample gates above, its score is promoted into the composite
          as a gated component. Otherwise it remains a side-by-side comparison on each signal.
        </p>
        <MLModelStatusTable />
      </Card>
    </div>
  );
}
