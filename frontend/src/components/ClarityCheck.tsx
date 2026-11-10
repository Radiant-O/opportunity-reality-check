import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import { ChevronRight, FileText, Lightbulb, LoaderCircle } from "lucide-react";
import { checkClarity, friendlyErrorMessage, isAbortError } from "../api";
import { CLARITY_STATUS } from "../status";
import type { Claim, ClarityRequest, ClarityResponse, JobSummary } from "../types";
import { ErrorCard } from "./ErrorCard";
import { EvidenceList, EvidenceQuote } from "./EvidenceList";
import { JobSearch } from "./JobSearch";
import { Segmented } from "./Segmented";
import { Skeleton } from "./Skeleton";
import { StatusBadge } from "./StatusBadge";

export const MAX_DESCRIPTION_CHARS = 15000;

export const SAMPLE_DESCRIPTION = `Founding Full-Stack Engineer — Lumen Labs (Seed, a16z speedrun)

Lumen Labs builds reconciliation tooling for finance teams at fast-growing startups. We're a team of six, backed by top-tier investors, and we're hiring our first full-stack engineer.

What you'll do
- Own features end to end, from Postgres schema to React UI
- Ship weekly with direct input from design partners
- Help shape our engineering culture and hiring bar

What we're looking for
- 4+ years building production web apps with TypeScript and React
- Comfortable with Python or Go on the backend
- Experience with AWS and CI/CD

Where we work
We're a hybrid team based in San Francisco. We work together in our SoMa office 3 days a week, Tuesday through Thursday.

This is a full-time role. Salary range $170k–$210k plus meaningful equity.`;

type Source = "paste" | "live";

const SOURCE_OPTIONS = [
  { value: "paste", label: "Paste description" },
  { value: "live", label: "Use a live listing" },
] as const;

const WORKPLACE_OPTIONS = [
  { value: "", label: "Not specified" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "Onsite" },
] as const;

const EMPLOYMENT_OPTIONS = [
  { value: "", label: "Not specified" },
  { value: "full_time", label: "Full time" },
  { value: "part_time", label: "Part time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
  { value: "temporary", label: "Temporary" },
] as const;

const numberFmt = new Intl.NumberFormat("en-US");

function ClarityResult({ result }: { result: ClarityResponse }) {
  const claimsById = useMemo(() => {
    const m = new Map<string, Claim>();
    for (const c of result.extraction.claims) m.set(c.id, c);
    return m;
  }, [result.extraction.claims]);

  return (
    <div className="animate-fade-in space-y-3">
      <section aria-labelledby="clarity-score" className="card p-4 sm:p-5">
        <p className="eyebrow">Result{result.job ? ` · ${result.job.title} at ${result.job.company}` : ""}</p>
        <h3 id="clarity-score" className="mt-1 text-[18px] font-semibold tracking-[-0.01em]">
          {result.clear_count} of {result.total} essentials are clear
        </h3>
        <ol className="mt-2 flex gap-1" aria-hidden="true">
          {result.items.map((it) => (
            <li
              key={it.dimension}
              className={`h-1.5 flex-1 rounded-full ${
                it.status === "clear" ? "bg-ok" : it.status === "partial" ? "bg-warn/70" : "border-bad-line border border-dashed bg-transparent"
              }`}
            />
          ))}
        </ol>
        <ul className="divide-line mt-4 divide-y">
          {result.items.map((it) => {
            const claims = (it.evidence_claim_ids ?? []).map((id) => claimsById.get(id)).filter((c): c is Claim => Boolean(c));
            return (
              <li key={it.dimension} className="py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[14px] font-semibold">{it.label}</p>
                  <StatusBadge meta={CLARITY_STATUS[it.status]} />
                </div>
                <p className="text-ink-2 mt-0.5 text-[13px] leading-relaxed">{it.detail}</p>
                {it.suggestion && (
                  <p className="border-accent/20 bg-accent-soft text-ink mt-2 flex gap-2 rounded-lg border px-2.5 py-2 text-[12.5px] leading-relaxed">
                    <Lightbulb aria-hidden="true" className="text-accent mt-0.5 size-3.5 shrink-0" />
                    <span>
                      <span className="font-medium">Suggestion: </span>
                      {it.suggestion}
                    </span>
                  </p>
                )}
                {claims.length > 0 && (
                  <details className="group mt-1.5">
                    <summary className="text-accent hover:text-accent-hover inline-flex items-center gap-0.5 rounded text-[12.5px] font-medium">
                      <ChevronRight aria-hidden="true" className="size-3.5 transition-transform duration-150 group-open:rotate-90" />
                      Evidence ({claims.length})
                    </summary>
                    <div className="mt-1.5 space-y-1.5">
                      {claims.map((c) => (
                        <EvidenceQuote key={c.id} claim={c} />
                      ))}
                    </div>
                  </details>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <details className="card group">
        <summary className="flex items-center gap-2 rounded-[var(--radius-card)] px-4 py-3">
          <ChevronRight aria-hidden="true" className="text-ink-2 size-4 transition-transform duration-150 group-open:rotate-90" />
          <span className="text-[14px] font-semibold">Evidence & uncertainty</span>
        </summary>
        <div className="border-line border-t px-4 py-4">
          <EvidenceList extraction={result.extraction} />
        </div>
      </details>

      <p className="text-ink-2 px-1 text-[12px] leading-relaxed">{result.note}</p>
    </div>
  );
}

export function ClarityCheck() {
  const [source, setSource] = useState<Source>("paste");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [workplace, setWorkplace] = useState("");
  const [employment, setEmployment] = useState("");
  const [liveJob, setLiveJob] = useState<JobSummary | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [result, setResult] = useState<ClarityResponse | null>(null);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const controllerRef = useRef<AbortController | null>(null);

  const descId = useId();
  const counterId = useId();
  const locId = useId();
  const wpId = useId();
  const empId = useId();
  const formErrorId = useId();

  useEffect(() => () => controllerRef.current?.abort(), []);

  function buildRequest(): ClarityRequest | null {
    if (source === "live") {
      if (!liveJob) {
        setFormError("Pick a listing first.");
        return null;
      }
      return { job_id: liveJob.id };
    }
    const text = description.trim();
    if (text.length < 40) {
      setFormError("Paste a job description (at least a few sentences).");
      return null;
    }
    return {
      description_text: text,
      location: location.trim() || null,
      workplace_type: workplace || null,
      employment_type: employment || null,
    };
  }

  function submit(e?: FormEvent) {
    e?.preventDefault();
    setFormError("");
    const body = buildRequest();
    if (!body) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setStatus("loading");
    checkClarity(body, controller.signal)
      .then((res) => {
        setResult(res);
        setStatus("success");
      })
      .catch((err: unknown) => {
        if (isAbortError(err)) return;
        setError(friendlyErrorMessage(err));
        setStatus("error");
      });
  }

  function loadSample() {
    setSource("paste");
    setDescription(SAMPLE_DESCRIPTION);
    setLocation("San Francisco, CA");
    setWorkplace("hybrid");
    setEmployment("full_time");
    setFormError("");
  }

  const canSubmit = status !== "loading";

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)] lg:items-start">
      <div className="space-y-4">
        <section aria-labelledby="clarity-title" className="card p-4">
          <p className="eyebrow">For founders & hiring managers</p>
          <h2 id="clarity-title" className="mt-0.5 text-[15px] font-semibold">
            Listing Clarity Check
          </h2>
          <p className="text-ink-2 mt-1 text-[13px] leading-relaxed">
            Paste a job description (or pick a live listing) to see which candidate-critical details are clear, partial or missing. We
            report gaps — we never assume your policy.
          </p>

          <form className="mt-4 space-y-3.5" onSubmit={submit} noValidate>
            <Segmented legend="Listing source" hideLegend name="clarity-source" value={source} options={SOURCE_OPTIONS} onChange={setSource} size="sm" />

            {source === "paste" ? (
              <>
                <div>
                  <div className="mb-1 flex items-end justify-between gap-2">
                    <label htmlFor={descId} className="text-[13px] font-medium">
                      Job description
                    </label>
                    <button type="button" className="btn-ghost -mr-2 px-2 py-0.5 text-[12.5px]" onClick={loadSample}>
                      <FileText aria-hidden="true" className="size-3.5" />
                      Load sample description
                    </button>
                  </div>
                  <textarea
                    id={descId}
                    value={description}
                    onChange={(e) => setDescription(e.target.value.slice(0, MAX_DESCRIPTION_CHARS))}
                    maxLength={MAX_DESCRIPTION_CHARS}
                    rows={12}
                    aria-describedby={`${counterId}${formError ? ` ${formErrorId}` : ""}`}
                    aria-invalid={Boolean(formError) || undefined}
                    placeholder="Paste the full job description here…"
                    className="input resize-y font-mono text-[12.5px] leading-relaxed"
                  />
                  <p id={counterId} className="text-ink-3 mt-1 text-right font-mono text-[11px]">
                    {numberFmt.format(description.length)} / {numberFmt.format(MAX_DESCRIPTION_CHARS)}
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="sm:col-span-3">
                    <label htmlFor={locId} className="label">
                      Location <span className="text-ink-3 font-normal">(optional)</span>
                    </label>
                    <input
                      id={locId}
                      className="input"
                      value={location}
                      maxLength={200}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="e.g. San Francisco, CA"
                    />
                  </div>
                  <div className="sm:col-span-3 grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor={wpId} className="label">
                        Workplace type
                      </label>
                      <select id={wpId} className="input" value={workplace} onChange={(e) => setWorkplace(e.target.value)}>
                        {WORKPLACE_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label htmlFor={empId} className="label">
                        Employment type
                      </label>
                      <select id={empId} className="input" value={employment} onChange={(e) => setEmployment(e.target.value)}>
                        {EMPLOYMENT_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-ink-2 text-[13px]">
                {liveJob ? (
                  <>
                    Selected: <span className="text-ink font-medium">{liveJob.title}</span> at {liveJob.company}
                  </>
                ) : (
                  "Choose a listing below."
                )}
              </p>
            )}

            {formError && (
              <p id={formErrorId} role="alert" className="text-bad text-[12.5px] font-medium">
                {formError}
              </p>
            )}

            <button type="submit" className="btn-primary w-full py-2" disabled={!canSubmit}>
              {status === "loading" && <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />}
              {status === "loading" ? "Checking…" : "Check clarity"}
            </button>
          </form>
        </section>

        {source === "live" && (
          <JobSearch
            name="clarity-job-search"
            eyebrow="Live listing"
            heading="Pick a listing"
            selectedId={liveJob?.id ?? null}
            onSelect={(j) => {
              setLiveJob(j);
              setFormError("");
            }}
          />
        )}
      </div>

      <div aria-busy={status === "loading"}>
        <p className="sr-only" aria-live="polite">
          {status === "loading"
            ? "Checking listing clarity…"
            : status === "success" && result
              ? `${result.clear_count} of ${result.total} essentials are clear.`
              : status === "error"
                ? "Clarity check failed."
                : ""}
        </p>
        {status === "idle" && (
          <div className="card p-5">
            <p className="eyebrow">What we check</p>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2">
              {["Location", "Work arrangement", "Relocation", "Visa sponsorship", "Employment type"].map((d) => (
                <li key={d} className="border-line bg-subtle rounded-lg border px-3 py-2 text-[13px] font-medium">
                  {d}
                </li>
              ))}
            </ul>
            <p className="text-ink-2 mt-3 text-[12.5px] leading-relaxed">
              Candidates filter on these five details first. When a listing is silent, strong applicants from other countries often skip it
              rather than ask.
            </p>
          </div>
        )}
        {status === "loading" && (
          <div className="card space-y-3 p-5">
            <p className="text-ink-2 text-[13px] font-medium">Reading the listing…</p>
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i}>
                <Skeleton className="h-3.5 w-1/3" />
                <Skeleton className="mt-1.5 h-3 w-5/6" />
              </div>
            ))}
          </div>
        )}
        {status === "error" && <ErrorCard title="Clarity check failed" message={error} onRetry={() => submit()} />}
        {status === "success" && result && <ClarityResult result={result} />}
      </div>
    </div>
  );
}
