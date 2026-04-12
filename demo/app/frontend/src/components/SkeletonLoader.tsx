interface SkeletonLoaderProps {
  rows?: number;
}

export default function SkeletonLoader({ rows = 3 }: SkeletonLoaderProps) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="h-4 bg-gray-100 rounded"
          style={{ width: `${80 - i * 10}%` }}
        />
      ))}
    </div>
  );
}
