import { Skeleton } from './ui/skeleton';

interface SkeletonTableProps {
  rows?: number;
  className?: string;
}

export function SkeletonTable({ rows = 5, className = '' }: SkeletonTableProps) {
  return (
    <div className={`w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950/70 p-4 ${className}`}>
      {/* Table Header Placeholder */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
        <Skeleton className="h-4 w-32 bg-slate-800/70" />
        <div className="flex gap-2">
          <Skeleton className="h-4 w-16 bg-slate-800/50" />
          <Skeleton className="h-4 w-20 bg-slate-800/50" />
        </div>
      </div>

      {/* Table Mock Column Header */}
      <div className="grid grid-cols-12 gap-3 py-2 px-3 mb-2 rounded-lg bg-slate-900/60 font-mono text-xs">
        <div className="col-span-2">
          <Skeleton className="h-3 w-16 bg-slate-800/80" />
        </div>
        <div className="col-span-3">
          <Skeleton className="h-3 w-24 bg-slate-800/80" />
        </div>
        <div className="col-span-3">
          <Skeleton className="h-3 w-28 bg-slate-800/80" />
        </div>
        <div className="col-span-2">
          <Skeleton className="h-3 w-14 bg-slate-800/80" />
        </div>
        <div className="col-span-2 text-right flex justify-end">
          <Skeleton className="h-3 w-16 bg-slate-800/80" />
        </div>
      </div>

      {/* Shimmering Mock Rows */}
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className="grid grid-cols-12 gap-3 items-center py-2.5 px-3 rounded-lg border border-slate-800/50 bg-slate-900/30"
          >
            {/* Timestamp */}
            <div className="col-span-2 flex items-center gap-1.5">
              <Skeleton className="h-2 w-2 rounded-full bg-slate-700" />
              <Skeleton className="h-3 w-20 bg-slate-800/80" />
            </div>

            {/* Monospace IP */}
            <div className="col-span-3 flex items-center gap-2">
              <Skeleton className="h-3 w-28 font-mono bg-slate-800/90" />
              <Skeleton className="h-3 w-10 rounded bg-slate-800/50" />
            </div>

            {/* Path / Resource */}
            <div className="col-span-3">
              <Skeleton className="h-3.5 w-3/4 bg-slate-800/70" />
            </div>

            {/* Decision Pill */}
            <div className="col-span-2">
              <Skeleton className="h-5 w-20 rounded-full bg-slate-800/90 border border-slate-700/40" />
            </div>

            {/* Layer / Action */}
            <div className="col-span-2 flex justify-end">
              <Skeleton className="h-4 w-12 rounded bg-slate-800/60" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SkeletonTable;
