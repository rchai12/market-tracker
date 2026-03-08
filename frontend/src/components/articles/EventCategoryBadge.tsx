interface EventCategoryBadgeProps {
  category: string;
  size?: "sm" | "md";
}

const CATEGORY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  earnings: { bg: "bg-blue-100 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-400", label: "Earnings" },
  merger_acquisition: { bg: "bg-purple-100 dark:bg-purple-900/30", text: "text-purple-700 dark:text-purple-400", label: "M&A" },
  regulatory: { bg: "bg-orange-100 dark:bg-orange-900/30", text: "text-orange-700 dark:text-orange-400", label: "Regulatory" },
  product_launch: { bg: "bg-teal-100 dark:bg-teal-900/30", text: "text-teal-700 dark:text-teal-400", label: "Product" },
  analyst_rating: { bg: "bg-indigo-100 dark:bg-indigo-900/30", text: "text-indigo-700 dark:text-indigo-400", label: "Analyst" },
  insider_trade: { bg: "bg-amber-100 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-400", label: "Insider" },
  macro_economic: { bg: "bg-slate-100 dark:bg-slate-700/50", text: "text-slate-700 dark:text-slate-300", label: "Macro" },
  legal: { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400", label: "Legal" },
  dividend: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400", label: "Dividend" },
  general_news: { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-600 dark:text-gray-300", label: "General" },
};

const DEFAULT_STYLE = { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-600 dark:text-gray-300", label: "Unknown" };

export default function EventCategoryBadge({ category, size = "sm" }: EventCategoryBadgeProps) {
  const style = CATEGORY_STYLES[category] ?? DEFAULT_STYLE;
  const sizeClasses = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${style.bg} ${style.text} ${sizeClasses}`}>
      {style.label}
    </span>
  );
}

export { CATEGORY_STYLES };
