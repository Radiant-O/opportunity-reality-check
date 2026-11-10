import { ExternalLink } from "lucide-react";

export function LogoMark({ className = "size-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="#2448E0" />
      <circle cx="14" cy="14" r="7" fill="none" stroke="#fff" strokeWidth="2.5" />
      <path d="M19.2 19.2 25 25" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
      <path d="m10.8 14.2 2.2 2.2 4.2-4.4" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Header() {
  return (
    <header className="border-line bg-surface/85 sticky top-0 z-20 border-b backdrop-blur">
      <div className="mx-auto flex h-13 max-w-[1240px] items-center gap-3 px-4 sm:px-6">
        <a href="#main" className="flex min-w-0 items-center gap-2.5 rounded-md">
          <LogoMark />
          <span className="min-w-0">
            <span className="block truncate text-[14.5px] leading-tight font-semibold tracking-[-0.01em]">
              Opportunity Reality Check
            </span>
            <span className="text-ink-2 hidden truncate text-[12px] leading-tight sm:block">
              What the listing actually says — before you apply
            </span>
          </span>
        </a>
        <span className="border-line-strong text-ink-2 ml-1 hidden shrink-0 rounded-full border px-2 py-px font-mono text-[10.5px] tracking-[0.04em] uppercase md:inline-block">
          Independent demo
        </span>
        <a
          href="https://speedrun-talent-network.com/jobs"
          target="_blank"
          rel="noopener noreferrer"
          className="text-ink-2 hover:text-accent ml-auto inline-flex shrink-0 items-center gap-1 rounded-md text-[13px] font-medium transition-colors"
        >
          <span className="hidden sm:inline">speedrun jobs</span>
          <span className="sm:hidden">Jobs</span>
          <ExternalLink aria-hidden="true" className="size-3.5" />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-line mt-12 border-t">
      <div className="text-ink-2 mx-auto flex max-w-[1240px] flex-col gap-1.5 px-4 py-6 text-[12.5px] sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>
          <span className="text-ink font-medium">Independent demo · not affiliated with a16z speedrun.</span> Informational only —
          not legal or immigration advice.
        </p>
        <p className="font-mono text-[11.5px]">Data: speedrun talent network API</p>
      </div>
    </footer>
  );
}
