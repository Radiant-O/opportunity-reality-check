import { useId, useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";

export const MAX_SKILLS = 20;
const MAX_SKILL_LEN = 40;

interface SkillsInputProps {
  value: string[];
  onChange: (skills: string[]) => void;
  label?: string;
}

export function SkillsInput({ value, onChange, label = "Skills (optional)" }: SkillsInputProps) {
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const hintId = useId();
  const atMax = value.length >= MAX_SKILLS;

  function add(raw: string) {
    const parts = raw
      .split(",")
      .map((s) => s.trim().slice(0, MAX_SKILL_LEN))
      .filter(Boolean);
    setDraft("");
    if (!parts.length) return;
    const next = [...value];
    for (const p of parts) {
      if (next.length >= MAX_SKILLS) break;
      if (!next.some((s) => s.toLowerCase() === p.toLowerCase())) next.push(p);
    }
    if (next.length !== value.length) onChange(next);
  }

  function remove(skill: string) {
    onChange(value.filter((s) => s !== skill));
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      e.preventDefault();
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div>
      <label htmlFor={inputId} className="label">
        {label}
      </label>
      <div className="border-line-strong bg-surface focus-within:border-accent flex flex-wrap items-center gap-1.5 rounded-lg border p-1.5 transition-colors focus-within:ring-2 focus-within:ring-[#2448e0]/20">
        {value.length > 0 && (
          <ul className="contents" aria-label="Added skills">
            {value.map((s) => (
              <li
                key={s}
                className="border-line bg-subtle text-ink inline-flex max-w-full items-center gap-0.5 rounded-md border py-px pr-0.5 pl-1.5 text-[12.5px]"
              >
                <span className="truncate">{s}</span>
                <button
                  type="button"
                  onClick={() => remove(s)}
                  aria-label={`Remove ${s}`}
                  className="text-ink-3 hover:text-ink hover:bg-neutral-bg rounded p-0.5"
                >
                  <X aria-hidden="true" className="size-3" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <input
          id={inputId}
          type="text"
          value={draft}
          disabled={atMax}
          onChange={(e) => {
            const v = e.target.value;
            if (v.includes(",")) add(v);
            else setDraft(v);
          }}
          onKeyDown={onKeyDown}
          onBlur={() => {
            if (draft.trim()) add(draft);
          }}
          placeholder={atMax ? "Maximum reached" : value.length ? "Add another…" : "e.g. TypeScript, React, Python"}
          aria-describedby={hintId}
          className="placeholder:text-ink-3 min-w-[8rem] flex-1 bg-transparent px-1 py-0.5 text-[14px] outline-none focus-visible:outline-none"
          autoComplete="off"
        />
      </div>
      <p id={hintId} className="text-ink-2 mt-1 text-[12px]">
        Enter or comma to add · Backspace removes the last · {value.length}/{MAX_SKILLS}
      </p>
    </div>
  );
}
