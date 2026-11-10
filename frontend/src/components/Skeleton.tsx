interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return <div aria-hidden="true" className={`animate-pulse rounded-md bg-[#eceae5] ${className}`} />;
}

export function JobCardSkeleton() {
  return (
    <div aria-hidden="true" className="border-line rounded-lg border p-3">
      <Skeleton className="h-3.5 w-3/4" />
      <Skeleton className="mt-2 h-3 w-1/2" />
      <div className="mt-3 flex gap-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}
