import LoadingSkeleton from "./LoadingSkeleton";
import ErrorRetry from "./ErrorRetry";

interface QueryGuardProps<T> {
  data: T | undefined;
  isLoading: boolean;
  isError?: boolean;
  refetch?: () => void;
  loadingVariant?: "card" | "row" | "chart";
  loadingCount?: number;
  errorMessage?: string;
  emptyMessage?: string;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
}

export default function QueryGuard<T>({
  data,
  isLoading,
  isError,
  refetch,
  loadingVariant = "card",
  loadingCount = 3,
  errorMessage,
  emptyMessage,
  isEmpty,
  children,
}: QueryGuardProps<T>) {
  if (isLoading) {
    return <LoadingSkeleton variant={loadingVariant} count={loadingCount} />;
  }

  if (isError && refetch) {
    return <ErrorRetry message={errorMessage} onRetry={() => refetch()} />;
  }

  if (data === undefined || data === null) {
    return emptyMessage ? (
      <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
        {emptyMessage}
      </p>
    ) : null;
  }

  if (isEmpty && isEmpty(data)) {
    return emptyMessage ? (
      <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
        {emptyMessage}
      </p>
    ) : null;
  }

  return <>{children(data)}</>;
}
