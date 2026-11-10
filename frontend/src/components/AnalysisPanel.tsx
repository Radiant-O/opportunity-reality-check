import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Briefcase, ChevronRight, CircleAlert, MapPin, Play, RefreshCw, Wallet } from "lucide-react";
import { analyze, friendlyErrorMessage, getJob, isAbortError } from "../api";
import { AUTH_LABEL, FINDING_STATUS, SECTION_STATUS, TECHNICAL_STATUS, humanize, type StatusMeta } from "../status";
import type { AnalysisResponse, Claim, JobDetail, JobSummary, SkillMatch } from "../types";
import { DraftInquiry } from "./DraftInquiry";
import { ErrorCard } from "./ErrorCard";
import { EvidenceList } from "./EvidenceList";
import { FindingList } from "./FindingList";
import { ExternalLinkText, WorkplaceBadge } from "./JobCard";
import { NextSteps } from "./NextSteps";
import { toCandidatePreferences, type Preferences } from "./PreferencesForm";
import { Skeleton } from "./Skeleton";
import { StatusBadge } from "./StatusBadge";

const LOADING_STEPS = [
  "Fetching full listing…",
  "Extracting statements…",
  "Checking evidence…",
  "Applying rules…",
] as const;

const WORK_LABEL: Record<Preferences["work_arrangement"], string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "Onsite",
  flexible: "Flexible on arrangement",
};
const RELOCATION_LABEL: Record<Preferences["relocation"], string> = {
  yes: "open to relocating",
  no: "not relocating",
  conditional: "relocation depends",
};
const SPONSORSHIP_LABEL: Record<Preferences["sponsorship"], string> = {
  yes: "needs sponsorship",
  no: "no sponsorship needed",
  unsure: "sponsorship unsure",
};

// ---------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------

function SectionCard({
  eyebrow,
  title,
  meta,
  headline,
  children,
  className = "",
}: {
  eyebrow: string;
  title: string;
  meta: StatusMeta;
  headline: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-label={title} className={`card animate-fade-in flex flex-col p-4 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="eyebrow">{eyebrow}</p>
          <h3 className="mt-0.5 text-[15px] font-semibold">{title}</h3>
        </div>
        <StatusBadge meta={meta} size="md" />
      </div>
      <p className="text-ink mt-2 text-[14px] leading-snug">{headline}</p>
      <div className="border-line mt-3 border-t pt-3">{children}</div>
    </section>
  );
}

function SkillChips({
  label,
  items,
  variant,
}: {
  label: string;
  items: string[];
  variant: "matched" | "listed" | "provided";
}) {
  if (items.length === 0) return null;
  const cls =
    variant === "matched"
      ? "bg-ok-bg text-ok border-ok-line"
      : variant === "listed"
        ? "bg-subtle text-ink-2 border-line"
        : "bg-surface text-ink-2 border-line-strong border-dashed";
  return (
    <div>
      <p className="text-ink-2 mb-1.5 text-[12px] font-medium">{label}</p>
      <ul className="flex flex-wrap gap-1.5" aria-label={label}>
        {items.map((s) => (
          <li key={s} className={`rounded-md border px-1.5 py-px text-[12.5px] ${cls}`}>
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Disclosure({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <details className="card group">
      <summary className="flex items-center gap-2 rounded-[var(--radius-card)] px-4 py-3">
        <ChevronRight aria-hidden="true" className="text-ink-2 size-4 transition-transform duration-150 group-open:rotate-90" />
        <span className="text-[14px] font-semibold">{title}</span>
        {hint && <span className="text-ink-2 ml-auto hidden text-[12px] sm:inline">{hint}</span>}
      </summary>
      <div className="border-line border-t px-4 py-4">{children}</div>
    </details>
  );
}

function LegendRow({ title, metas }: { title: string; metas: StatusMeta[] }) {
  return (
    <div>
      <p className="eyebrow mb-1.5">{title}</p>
      <ul className="flex flex-wrap gap-1.5">
        {metas.map((m) => (
          <li key={m.label}>
            <StatusBadge meta={m} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function EmptyState() {
  const sections = [
    {
      title: "Location & work arrangement",
      text: "Where the role is based, whether it is remote, hybrid or onsite, and any country restrictions — compared with where you live.",
    },
    {
      title: "Work authorization & sponsorship",
      text: "Only what the listing explicitly says about visas and sponsorship. Silence is reported as “Not specified”, never as “No”.",
    },
    {
      title: "Technical alignment",
      text: "Skills the listing names that overlap with yours. Supporting context, not a hiring decision.",
    },
  ];
  return (
    <div className="card p-5 sm:p-6">
      <p className="eyebrow">Analysis</p>
      <h2 className="mt-0.5 text-[17px] font-semibold">Pick a role to reality-check</h2>
      <p className="text-ink-2 mt-1 max-w-[60ch] text-[13.5px]">
        Fill in your situation, choose a listing, then run the check. You’ll get three short sections, each backed by quotes from the
        listing.
      </p>
      <ol className="mt-5 grid gap-3 md:grid-cols-3">
        {sections.map((s, i) => (
          <li key={s.title} className="border-line bg-subtle rounded-[10px] border p-3.5">
            <span className="text-accent font-mono text-[11px] font-medium">0{i + 1}</span>
            <p className="mt-1 text-[13.5px] font-semibold">{s.title}</p>
            <p className="text-ink-2 mt-1 text-[12.5px] leading-relaxed">{s.text}</p>
          </li>
        ))}
      </ol>
      <div className="border-line mt-5 space-y-3 border-t pt-4">
        <LegendRow
          title="Sponsorship labels"
          metas={[
            { ...AUTH_LABEL.explicitly_supported, label: "Supported" },
            { ...AUTH_LABEL.explicitly_restricted, label: "Restricted" },
            AUTH_LABEL.not_specified,
            AUTH_LABEL.needs_clarification,
          ]}
        />
        <LegendRow
          title="Finding labels"
          metas={[FINDING_STATUS.agreement, FINDING_STATUS.conflict, FINDING_STATUS.unknown, FINDING_STATUS.caution]}
        />
      </div>
    </div>
  );
}

function LoadingState() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, LOADING_STEPS.length - 1)), 1400);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="space-y-3" aria-busy="true">
      <div className="card p-4">
        <p className="text-ink-2 flex items-center gap-2 text-[13px] font-medium">
          <span className="bg-accent size-1.5 animate-pulse rounded-full" aria-hidden="true" />
          {LOADING_STEPS[step]}
        </p>
        <Skeleton className="mt-3 h-4 w-11/12" />
        <Skeleton className="mt-2 h-4 w-2/3" />
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="card p-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-2 h-4 w-48" />
            <Skeleton className="mt-4 h-3 w-full" />
            <Skeleton className="mt-2 h-3 w-5/6" />
            <Skeleton className="mt-2 h-3 w-4/6" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result
// ---------------------------------------------------------------------------

function AnalysisResult({ result }: { result: AnalysisResponse }) {
  const claimsById = useMemo(() => {
    const m = new Map<string, Claim>();
    for (const c of result.extraction.claims) m.set(c.id, c);
    return m;
  }, [result.extraction.claims]);

  const { location, authorization, technical } = result;
  const skillNames = (xs: SkillMatch[] | undefined) => (xs ?? []).map((s) => s.skill);
  const locationFacts = [location.job_location, location.job_country, location.work_arrangement ? humanize(location.work_arrangement) : null]
    .filter((x): x is string => Boolean(x))
    .filter((x, i, arr) => arr.indexOf(x) === i);

  return (
    <div className="space-y-3">
      <section aria-labelledby="assessment-title" className="border-accent/25 bg-accent-soft animate-fade-in rounded-[var(--radius-card)] border p-4">
        <p id="assessment-title" className="eyebrow text-accent">
          Assessment
        </p>
        <p className="text-ink mt-1 text-[15px] leading-relaxed font-medium">{result.assessment}</p>
      </section>

      <div className="grid gap-3 xl:grid-cols-2">
        <SectionCard
          eyebrow="Section 1"
          title="Location & work arrangement"
          meta={SECTION_STATUS[location.status]}
          headline={location.headline}
        >
          {locationFacts.length > 0 && (
            <p className="text-ink-2 mb-3 flex items-center gap-1.5 font-mono text-[11.5px]">
              <MapPin aria-hidden="true" className="size-3.5 shrink-0" />
              {locationFacts.join(" · ")}
            </p>
          )}
          <FindingList findings={location.findings} claimsById={claimsById} />
        </SectionCard>

        <SectionCard
          eyebrow="Section 2"
          title="Work authorization & sponsorship"
          meta={AUTH_LABEL[authorization.label]}
          headline={authorization.headline}
        >
          <FindingList findings={authorization.findings} claimsById={claimsById} />
          <p className="text-ink-2 border-line mt-3 border-t border-dashed pt-2.5 text-[12px] leading-relaxed">{authorization.note}</p>
        </SectionCard>

        <SectionCard
          eyebrow="Section 3 · supporting info"
          title="Technical alignment"
          meta={TECHNICAL_STATUS[technical.status]}
          headline={technical.headline}
          className="xl:col-span-2"
        >
          <div className="space-y-3">
            <SkillChips label="Matched — listed and provided" items={skillNames(technical.matched)} variant="matched" />
            <SkillChips label="Listed, not in your skills" items={skillNames(technical.listed_not_provided)} variant="listed" />
            <SkillChips label="Yours, not mentioned in the listing" items={technical.provided_not_listed ?? []} variant="provided" />
            <p className="text-ink-2 text-[12px] leading-relaxed">
              {technical.note}
            </p>
          </div>
        </SectionCard>
      </div>

      <section aria-labelledby="next-steps-title" className="card animate-fade-in p-4">
        <p className="eyebrow">Before you apply</p>
        <h3 id="next-steps-title" className="mt-0.5 mb-2 text-[15px] font-semibold">
          Next steps
        </h3>
        <NextSteps steps={result.next_steps} />
      </section>

      <section aria-labelledby="draft-title" className="card animate-fade-in p-4">
        <p className="eyebrow">Optional</p>
        <h3 id="draft-title" className="mt-0.5 mb-2 text-[15px] font-semibold">
          Draft inquiry
        </h3>
        <DraftInquiry text={result.draft_inquiry} />
      </section>

      <Disclosure
        title="Evidence & uncertainty"
        hint={`${result.extraction.claims.length} quoted statements · ${(result.extraction.unknown_categories ?? []).length} not stated`}
      >
        <EvidenceList extraction={result.extraction} />
      </Disclosure>

      <p className="text-ink-2 flex gap-2 px-1 text-[12px] leading-relaxed">
        <CircleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        {result.disclaimer}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

function JobHeader({
  job,
  preferences,
  onRun,
  running,
  hasResult,
}: {
  job: JobSummary & Partial<JobDetail>;
  preferences: Preferences;
  onRun: () => void;
  running: boolean;
  hasResult: boolean;
}) {
  const prefSummary = [
    preferences.country.trim() || "Country not set",
    WORK_LABEL[preferences.work_arrangement],
    RELOCATION_LABEL[preferences.relocation],
    SPONSORSHIP_LABEL[preferences.sponsorship],
  ].join(" · ");

  return (
    <section aria-labelledby="job-title" className="card p-4 sm:p-5">
      <p className="eyebrow">Selected role</p>
      <h2 id="job-title" className="mt-1 text-[18px] leading-snug font-semibold tracking-[-0.01em]">
        {job.title}
      </h2>
      <p className="text-ink-2 mt-0.5 text-[14px]">{job.company}</p>
      <div className="text-ink-2 mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12.5px]">
        <WorkplaceBadge type={job.workplace_type} />
        {job.location && (
          <span className="inline-flex items-center gap-1">
            <MapPin aria-hidden="true" className="size-3.5" />
            {job.location}
          </span>
        )}
        {job.employment_type && (
          <span className="inline-flex items-center gap-1">
            <Briefcase aria-hidden="true" className="size-3.5" />
            {humanize(job.employment_type)}
          </span>
        )}
        {job.comp_summary && (
          <span className="inline-flex items-center gap-1">
            <Wallet aria-hidden="true" className="size-3.5" />
            {job.comp_summary}
          </span>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        <ExternalLinkText href={job.url}>Open original listing</ExternalLinkText>
        {job.apply_url && <ExternalLinkText href={job.apply_url}>Apply on official page</ExternalLinkText>}
      </div>

      <div className="border-line mt-4 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-ink-2 min-w-0 text-[12.5px]">
          <span className="text-ink font-medium">Checking as:</span> {prefSummary}
        </p>
        <button type="button" className="btn-primary shrink-0 px-4 py-2" onClick={onRun} disabled={running}>
          {hasResult ? <RefreshCw aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
          {running ? "Checking…" : hasResult ? "Re-run reality check" : "Run reality check"}
        </button>
      </div>
    </section>
  );
}

interface AnalysisPanelProps {
  job: JobSummary | null;
  preferences: Preferences;
}

type Status = "idle" | "loading" | "success" | "error";

export function AnalysisPanel({ job, preferences }: AnalysisPanelProps) {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [ranWith, setRanWith] = useState<string | null>(null);
  const runController = useRef<AbortController | null>(null);
  const jobId = job?.id ?? null;

  // Reset and fetch listing detail (comp, apply URL) whenever the selected job changes.
  useEffect(() => {
    runController.current?.abort();
    setStatus("idle");
    setResult(null);
    setDetail(null);
    setRanWith(null);
    if (!jobId) return;
    const controller = new AbortController();
    getJob(jobId, controller.signal)
      .then(setDetail)
      .catch(() => {
        // Non-critical: the header falls back to the summary fields.
      });
    return () => controller.abort();
  }, [jobId]);

  useEffect(() => () => runController.current?.abort(), []);

  const currentPrefsKey = JSON.stringify(toCandidatePreferences(preferences));
  const prefsChanged = status === "success" && ranWith !== null && ranWith !== currentPrefsKey;

  function run() {
    if (!job) return;
    runController.current?.abort();
    const controller = new AbortController();
    runController.current = controller;
    const prefs = toCandidatePreferences(preferences);
    setStatus("loading");
    setErrorMessage("");
    analyze({ job_id: job.id, preferences: prefs }, controller.signal)
      .then((res) => {
        setResult(res);
        setRanWith(JSON.stringify(prefs));
        setStatus("success");
      })
      .catch((err: unknown) => {
        if (isAbortError(err)) return;
        setErrorMessage(friendlyErrorMessage(err));
        setStatus("error");
      });
  }

  const liveText =
    status === "loading" ? "Running reality check…" : status === "success" ? "Reality check complete." : status === "error" ? "Reality check failed." : "";

  if (!job) return <EmptyState />;

  const headerJob: JobSummary & Partial<JobDetail> = result?.job ?? detail ?? job;

  return (
    <div className="space-y-3">
      <p className="sr-only" aria-live="polite">
        {liveText}
      </p>
      <JobHeader job={headerJob} preferences={preferences} onRun={run} running={status === "loading"} hasResult={status === "success"} />

      {prefsChanged && (
        <div
          role="status"
          className="border-line-strong bg-surface animate-fade-in flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-dashed px-3.5 py-2.5"
        >
          <p className="text-ink-2 text-[13px]">
            <span className="text-ink font-medium">Preferences changed — re-run</span> to update this result.
          </p>
          <button type="button" className="btn-ghost" onClick={run}>
            <RefreshCw aria-hidden="true" className="size-3.5" />
            Re-run
          </button>
        </div>
      )}

      {status === "idle" && (
        <div className="border-line text-ink-2 rounded-[var(--radius-card)] border border-dashed px-4 py-8 text-center text-[13.5px]">
          Ready when you are. The check reads the full listing, quotes what it says, and compares it with your situation.
        </div>
      )}
      {status === "loading" && <LoadingState />}
      {status === "error" && <ErrorCard title="Reality check failed" message={errorMessage} onRetry={run} />}
      {status === "success" && result && <AnalysisResult result={result} />}
    </div>
  );
}
