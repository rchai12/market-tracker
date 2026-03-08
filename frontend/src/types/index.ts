/**
 * Barrel re-export of all type modules.
 *
 * Consumers can continue importing from "@/types" or "../types".
 * For new code, prefer importing from the specific sub-module
 * (e.g., "@/types/signal") to keep dependencies explicit.
 */

export type { User, PaginatedResponse } from "./common";
export type { Stock, MarketDataDaily, IndicatorData } from "./stock";
export type { Article, EventCategorySummary } from "./article";
export type { SentimentScore, SentimentSummary, SentimentTimePoint } from "./sentiment";
export type {
  Signal,
  SignalAccuracy,
  SignalWeights,
  AccuracyTrendPoint,
  AccuracyBucket,
  AccuracyDistribution,
  SignalOutcome,
  LinkedArticle,
  SignalDetail,
} from "./signal";
export type { AlertConfig, AlertLog } from "./alert";
export type {
  BacktestConfig,
  BacktestSummary,
  EquityPoint,
  BacktestTrade,
  BacktestDetail,
} from "./backtest";
