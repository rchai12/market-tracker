interface LoadingSkeletonProps {
  variant: "card" | "row" | "chart";
  count?: number;
}

function SkeletonItem({ variant }: { variant: LoadingSkeletonProps["variant"] }) {
  if (variant === "card") {
    return <div className="bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse h-40" />;
  }
  if (variant === "chart") {
    return <div className="bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse h-48 w-full" />;
  }
  // row
  return (
    <div className="flex items-center gap-3 animate-pulse">
      <div className="bg-gray-200 dark:bg-gray-700 rounded h-4 w-1/4" />
      <div className="bg-gray-200 dark:bg-gray-700 rounded h-4 w-1/2" />
      <div className="bg-gray-200 dark:bg-gray-700 rounded h-4 w-1/6" />
    </div>
  );
}

export default function LoadingSkeleton({ variant, count = 1 }: LoadingSkeletonProps) {
  const items = Array.from({ length: count }, (_, i) => (
    <SkeletonItem key={i} variant={variant} />
  ));

  if (variant === "card" && count > 1) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items}
      </div>
    );
  }

  return <div className="space-y-3">{items}</div>;
}
