import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listStocks } from "../../api/stocks";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data } = useQuery({
    queryKey: ["stock-search", query],
    queryFn: () => listStocks({ search: query, per_page: 8 }),
    enabled: query.length >= 1,
    staleTime: 30_000,
  });

  const results = data?.data ?? [];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(ticker: string) {
    setQuery("");
    setIsOpen(false);
    navigate(`/stocks/${ticker}`);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      setIsOpen(false);
      setQuery("");
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <svg
          className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => query.length >= 1 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search stocks..."
          className="w-48 sm:w-64 pl-9 pr-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {isOpen && query.length >= 1 && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
          {results.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
              No stocks found
            </div>
          ) : (
            results.map((stock) => (
              <button
                key={stock.id}
                type="button"
                onClick={() => handleSelect(stock.ticker)}
                className="w-full text-left px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
              >
                <div>
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">
                    {stock.ticker}
                  </span>
                  <span className="text-sm text-gray-500 dark:text-gray-400 ml-2">
                    {stock.company_name}
                  </span>
                </div>
                {stock.sector_name && (
                  <span className="text-xs text-gray-400 dark:text-gray-500 ml-2 shrink-0">
                    {stock.sector_name}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
