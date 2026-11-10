import { RotateCw, TriangleAlert } from "lucide-react";

interface ErrorCardProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorCard({ title = "Something went wrong", message, onRetry, retryLabel = "Try again" }: ErrorCardProps) {
  return (
    <div role="alert" className="border-bad-line bg-bad-bg animate-fade-in flex items-start gap-3 rounded-[10px] border p-3.5">
      <TriangleAlert aria-hidden="true" className="text-bad mt-0.5 size-4 shrink-0" strokeWidth={2.25} />
      <div className="min-w-0 flex-1">
        <p className="text-bad text-[13.5px] font-semibold">{title}</p>
        <p className="text-ink mt-0.5 text-[13.5px]">{message}</p>
      </div>
      {onRetry && (
        <button type="button" className="btn-secondary shrink-0" onClick={onRetry}>
          <RotateCw aria-hidden="true" className="size-3.5" />
          {retryLabel}
        </button>
      )}
    </div>
  );
}
