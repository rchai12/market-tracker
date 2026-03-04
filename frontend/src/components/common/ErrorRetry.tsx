interface ErrorRetryProps {
  message?: string;
  onRetry: () => void;
}

export default function ErrorRetry({ message = "Failed to load data", onRetry }: ErrorRetryProps) {
  return (
    <div className="text-center py-4">
      <p className="text-red-500 dark:text-red-400 text-sm mb-2">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="px-3 py-1.5 text-sm rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400"
      >
        Retry
      </button>
    </div>
  );
}
