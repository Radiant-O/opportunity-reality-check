import { ArrowLeftRight, Building2, ExternalLink, Globe, MapPin } from "lucide-react";
import type { ReactNode } from "react";
import type { JobSummary, WorkplaceType } from "../types";

const WORKPLACE: Record<WorkplaceType, { label: string; icon: typeof Globe }> = {
  remote: { label: "Remote", icon: Globe },
  hybrid: { label: "Hybrid", icon: ArrowLeftRight },
  onsite: { label: "Onsite", icon: Building2 },
};

export function WorkplaceBadge({ type }: { type: WorkplaceType | null | undefined }) {
  if (!type) {
    return (
      <span className="border-line text-ink-3 inline-flex items-center rounded-md border border-dashed px-1.5 py-px text-[11.5px]">
        Workplace not set
      </span>
    );
  }
  const { label, icon: Icon } = WORKPLACE[type];
  return (
    <span className="border-line bg-subtle text-ink-2 inline-flex items-center gap-1 rounded-md border px-1.5 py-px text-[11.5px] font-medium">
      <Icon aria-hidden="true" className="size-3" />
      {label}
    </span>
  );
}

export function ExternalLinkText({ href, children, className = "" }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-accent hover:text-accent-hover inline-flex items-center gap-1 rounded text-[12.5px] font-medium hover:underline ${className}`}
    >
      {children}
      <ExternalLink aria-hidden="true" className="size-3" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

interface JobCardProps {
  job: JobSummary;
  selected: boolean;
  onSelect: (job: JobSummary) => void;
}

export function JobCard({ job, selected, onSelect }: JobCardProps) {
  return (
    <div
      className={`group rounded-lg border transition-colors duration-150 ${
        selected ? "border-accent bg-accent-soft/60 shadow-[0_0_0_1px_var(--color-accent)]" : "border-line bg-surface hover:border-line-strong"
      }`}
    >
      <button
        type="button"
        aria-pressed={selected}
        onClick={() => onSelect(job)}
        className="block w-full rounded-lg px-3 pt-2.5 pb-1.5 text-left"
      >
        <span className="text-ink block text-[14px] leading-snug font-semibold">{job.title}</span>
        <span className="text-ink-2 mt-0.5 block text-[13px]">{job.company}</span>
        <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          <WorkplaceBadge type={job.workplace_type} />
          {job.location && (
            <span className="text-ink-2 inline-flex min-w-0 items-center gap-1 text-[12px]">
              <MapPin aria-hidden="true" className="size-3 shrink-0" />
              <span className="truncate">{job.location}</span>
            </span>
          )}
        </span>
      </button>
      <div className="flex items-center justify-between px-3 pb-2">
        <span className={`text-[11.5px] font-medium ${selected ? "text-accent" : "text-transparent"}`} aria-hidden="true">
          Selected
        </span>
        <ExternalLinkText href={job.url}>View on speedrun</ExternalLinkText>
      </div>
    </div>
  );
}
