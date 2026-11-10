import type { StatusMeta, Tone } from "../status";

const TONE_CLASS: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok border-ok-line",
  bad: "bg-bad-bg text-bad border-bad-line",
  warn: "bg-warn-bg text-warn border-warn-line",
  neutral: "bg-neutral-bg text-neutral border-neutral-line",
  missing: "bg-surface text-bad border-bad-line border-dashed",
};

export const TONE_TEXT: Record<Tone, string> = {
  ok: "text-ok",
  bad: "text-bad",
  warn: "text-warn",
  neutral: "text-neutral",
  missing: "text-bad",
};

interface StatusBadgeProps {
  meta: StatusMeta;
  size?: "sm" | "md";
  className?: string;
}

/** Status is always communicated by icon + text, never color alone. */
export function StatusBadge({ meta, size = "sm", className = "" }: StatusBadgeProps) {
  const Icon = meta.icon;
  const sizing = size === "md" ? "px-2 py-0.5 text-[12.5px] gap-1.5" : "px-1.5 py-px text-[11.5px] gap-1";
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-md border font-medium whitespace-nowrap ${sizing} ${TONE_CLASS[meta.tone]} ${className}`}
    >
      <Icon aria-hidden="true" className={size === "md" ? "size-3.5" : "size-3"} strokeWidth={2.25} />
      {meta.label}
    </span>
  );
}
