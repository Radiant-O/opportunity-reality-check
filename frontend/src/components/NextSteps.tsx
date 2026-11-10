import { useState } from "react";
import type { NextStep, Priority } from "../types";

const PRIORITY_CLASS: Record<Priority, string> = {
  high: "text-ink border-ink/25",
  medium: "text-ink-2 border-line-strong",
  low: "text-ink-3 border-line",
};

interface NextStepsProps {
  steps: NextStep[];
}

/** Checklist; checked state is local to this view and never stored. */
export function NextSteps({ steps }: NextStepsProps) {
  const [done, setDone] = useState<ReadonlySet<string>>(() => new Set());

  if (steps.length === 0) return <p className="text-ink-2 text-[13px]">No follow-ups suggested.</p>;

  const toggle = (id: string) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <ul className="space-y-1">
      {steps.map((s) => {
        const checked = done.has(s.id);
        const inputId = `step-${s.id}`;
        return (
          <li key={s.id} className="hover:bg-subtle -mx-2 flex gap-2.5 rounded-lg px-2 py-2">
            <input
              id={inputId}
              type="checkbox"
              checked={checked}
              onChange={() => toggle(s.id)}
              className="accent-accent mt-0.5 size-4 shrink-0"
              aria-describedby={`${inputId}-reason`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
                <label htmlFor={inputId} className={`text-[13.5px] leading-snug font-medium ${checked ? "text-ink-3 line-through" : ""}`}>
                  {s.text}
                </label>
                <span
                  className={`shrink-0 rounded border px-1 font-mono text-[10.5px] tracking-[0.04em] uppercase ${PRIORITY_CLASS[s.priority]}`}
                >
                  {s.priority} priority
                </span>
              </div>
              <p id={`${inputId}-reason`} className="text-ink-2 mt-0.5 text-[12.5px]">
                {s.reason}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
