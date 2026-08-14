import { clsx } from 'clsx'

const Skeleton = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => {
  return (
    <div
      className={clsx(
        'animate-pulse rounded-md bg-surface',
        className
      )}
      {...props}
    />
  )
}

// Preset skeletons for common patterns
const MetricCardSkeleton = () => (
  <div className="space-y-3 p-4">
    <Skeleton className="h-4 w-20" />
    <Skeleton className="h-8 w-16" />
    <Skeleton className="h-3 w-24" />
  </div>
)

const TableRowSkeleton = ({ cols = 5 }: { cols?: number }) => (
  <div className="flex items-center gap-4 p-4 border-b border-border">
    {Array.from({ length: cols }).map((_, i) => (
      <Skeleton key={i} className="h-4 flex-1" />
    ))}
  </div>
)

const CardSkeleton = () => (
  <div className="rounded-lg border border-border p-6 space-y-4">
    <Skeleton className="h-6 w-32" />
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-3/4" />
    <div className="flex gap-2">
      <Skeleton className="h-8 w-20" />
      <Skeleton className="h-8 w-20" />
    </div>
  </div>
)

const ChartSkeleton = () => (
  <div className="rounded-lg border border-border p-6 space-y-4">
    <div className="flex justify-between">
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-4 w-24" />
    </div>
    <Skeleton className="h-[200px] w-full rounded-lg" />
  </div>
)

const WorkflowSkeleton = () => (
  <div className="space-y-4">
    <div className="flex items-center gap-4">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="space-y-2 flex-1">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-24" />
      </div>
      <Skeleton className="h-6 w-16" />
    </div>
    <div className="ml-5 pl-4 border-l-2 border-border space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-8 w-8 rounded-full" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  </div>
)

export { Skeleton, MetricCardSkeleton, TableRowSkeleton, CardSkeleton, ChartSkeleton, WorkflowSkeleton }
