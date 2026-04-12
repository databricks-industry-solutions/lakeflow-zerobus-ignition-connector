interface ConnectionBannerProps {
  connected: boolean;
}

export default function ConnectionBanner({ connected }: ConnectionBannerProps) {
  if (connected) return null;

  return (
    <div
      className="flex items-center justify-center gap-3 bg-red-50 border border-red-200 text-red-800 px-4 py-3 text-sm rounded-card mb-4 shadow-card transition-opacity duration-200"
      role="alert"
    >
      <span className="flex h-2.5 w-2.5 flex-shrink-0 rounded-full bg-red-500" aria-hidden />
      <span>Connection Lost — Unable to reach the Databricks backend</span>
    </div>
  );
}
