import { useId, type ReactNode } from "react";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  legend: string;
  name: string;
  value: T;
  options: readonly SegmentedOption<T>[];
  onChange: (value: T) => void;
  helper?: ReactNode;
  size?: "sm" | "md";
  /** Visually hide the legend (still announced). */
  hideLegend?: boolean;
}

/**
 * Segmented control built on native radio inputs, so arrow-key navigation,
 * form semantics and screen-reader announcements come for free.
 */
export function Segmented<T extends string>({
  legend,
  name,
  value,
  options,
  onChange,
  helper,
  size = "md",
  hideLegend = false,
}: SegmentedProps<T>) {
  const helperId = useId();
  return (
    <fieldset aria-describedby={helper ? helperId : undefined} className="min-w-0">
      <legend className={hideLegend ? "sr-only" : "label"}>{legend}</legend>
      <div className="border-line-strong bg-subtle flex rounded-lg border p-0.5">
        {options.map((o) => {
          const checked = o.value === value;
          return (
            <label
              key={o.value}
              className={`relative flex-1 rounded-md text-center font-medium whitespace-nowrap transition-colors duration-150 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-[#2448e0] ${
                size === "sm" ? "px-1.5 py-1 text-[12.5px]" : "px-2 py-1 text-[13px]"
              } ${
                checked
                  ? "bg-surface text-accent shadow-[0_0_0_1px_var(--color-line-strong),0_1px_2px_rgb(28_27_25/0.06)]"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={o.value}
                checked={checked}
                onChange={() => onChange(o.value)}
                className="sr-only"
              />
              {o.label}
            </label>
          );
        })}
      </div>
      {helper && (
        <p id={helperId} className="text-ink-2 mt-1.5 text-[12px] leading-snug">
          {helper}
        </p>
      )}
    </fieldset>
  );
}
