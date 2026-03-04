/** Shared UI constants for direction badges and signal strength styles. */

export const DIRECTION_COLORS: Record<string, { bg: string; text: string }> = {
  bullish: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400" },
  bearish: { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400" },
  neutral: { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-600 dark:text-gray-300" },
};

export const STRENGTH_STYLES: Record<string, string> = {
  strong: "border-l-4 border-l-yellow-500",
  moderate: "border-l-4 border-l-blue-400",
  weak: "border-l-2 border-l-gray-300 dark:border-l-gray-600",
};
