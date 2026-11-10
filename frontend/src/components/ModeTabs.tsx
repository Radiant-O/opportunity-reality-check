import { useRef, type KeyboardEvent } from "react";

export type Mode = "candidate" | "clarity";

const TABS: { id: Mode; label: string; hint: string }[] = [
  { id: "candidate", label: "Candidate check", hint: "for job seekers" },
  { id: "clarity", label: "Listing Clarity Check", hint: "for founders" },
];

export const tabId = (m: Mode) => `mode-tab-${m}`;
export const panelId = (m: Mode) => `mode-panel-${m}`;

interface ModeTabsProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeTabs({ mode, onChange }: ModeTabsProps) {
  const refs = useRef<Record<Mode, HTMLButtonElement | null>>({ candidate: null, clarity: null });

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const idx = TABS.findIndex((t) => t.id === mode);
    let next: number | null = null;
    if (e.key === "ArrowRight") next = (idx + 1) % TABS.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TABS.length - 1;
    if (next === null) return;
    e.preventDefault();
    const target = TABS[next]!;
    onChange(target.id);
    refs.current[target.id]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label="Mode"
      onKeyDown={onKeyDown}
      className="border-line bg-surface inline-flex w-full max-w-full rounded-[10px] border p-1 sm:w-auto"
    >
      {TABS.map((t) => {
        const selected = t.id === mode;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={tabId(t.id)}
            aria-selected={selected}
            aria-controls={panelId(t.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={`flex-1 rounded-[7px] px-3 py-1.5 text-left text-[13.5px] font-medium transition-colors duration-150 sm:flex-none ${
              selected ? "bg-accent text-white" : "text-ink-2 hover:text-ink hover:bg-subtle"
            }`}
          >
            {t.label}
            <span className={`ml-1.5 hidden text-[12px] font-normal sm:inline ${selected ? "text-white/75" : "text-ink-3"}`}>
              {t.hint}
            </span>
          </button>
        );
      })}
    </div>
  );
}
