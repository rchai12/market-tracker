import type { BacktestTrade } from "../../types";

interface TradeLogProps {
  trades: BacktestTrade[];
}

export default function TradeLog({ trades }: TradeLogProps) {
  if (trades.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
        No trades executed
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="pb-2 pr-4">Date</th>
            <th className="pb-2 pr-4">Ticker</th>
            <th className="pb-2 pr-4">Action</th>
            <th className="pb-2 pr-4 text-right">Price</th>
            <th className="pb-2 pr-4 text-right">Shares</th>
            <th className="pb-2 pr-4 text-right">Signal</th>
            <th className="pb-2 text-right">Return</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
          {trades.map((trade) => (
            <tr key={trade.id} className="text-gray-900 dark:text-gray-200">
              <td className="py-2 pr-4 whitespace-nowrap">
                {new Date(trade.trade_date).toLocaleDateString()}
              </td>
              <td className="py-2 pr-4 font-medium">{trade.ticker}</td>
              <td className="py-2 pr-4">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    trade.action === "buy"
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                  }`}
                >
                  {trade.action.toUpperCase()}
                </span>
              </td>
              <td className="py-2 pr-4 text-right">${trade.price.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right">{trade.shares.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {trade.signal_score.toFixed(3)}
                </span>
              </td>
              <td className="py-2 text-right">
                {trade.return_pct !== null ? (
                  <span
                    className={`font-medium ${
                      trade.return_pct >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {trade.return_pct >= 0 ? "+" : ""}
                    {trade.return_pct.toFixed(2)}%
                  </span>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
