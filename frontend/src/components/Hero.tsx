import { CircleHelp, Lock, Quote } from "lucide-react";

const PRINCIPLES = [
  { icon: Quote, text: "Quotes, not guesses" },
  { icon: CircleHelp, text: "Unknown ≠ No" },
  { icon: Lock, text: "Only the analysis request leaves your browser" },
] as const;

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="pt-8 pb-6 sm:pt-10">
      <p className="eyebrow">Opportunity Reality Check · Independent demo · not affiliated with a16z speedrun</p>
      <h1
        id="hero-title"
        className="mt-2 max-w-[760px] text-[24px] leading-[1.2] font-semibold tracking-[-0.02em] text-balance sm:text-[28px]"
      >
        Know what a job listing actually says about location, remote work and visa sponsorship — before you spend hours applying.
      </h1>
      <ul className="mt-4 flex flex-wrap gap-2" aria-label="Principles">
        {PRINCIPLES.map(({ icon: Icon, text }) => (
          <li
            key={text}
            className="border-line bg-surface text-ink-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12.5px]"
          >
            <Icon aria-hidden="true" className="text-accent size-3.5" />
            {text}
          </li>
        ))}
      </ul>
    </section>
  );
}
