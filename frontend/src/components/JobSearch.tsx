import { useCallback, useEffect, useId, useRef, useState } from "react";
import { LoaderCircle, Search } from "lucide-react";
import { friendlyErrorMessage, isAbortError, searchJobs } from "../api";
import { useDebounce } from "../hooks/useDebounce";
import type { JobListResponse, JobSummary, WorkplaceType } from "../types";
import { ErrorCard } from "./ErrorCard";
import { JobCard } from "./JobCard";
import { Segmented } from "./Segmented";
import { JobCardSkeleton } from "./Skeleton";

type WorkplaceFilter = "any" | WorkplaceType;

const WORKPLACE_FILTERS = [
  { value: "any", label: "Any" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "Onsite" },
] as const;

const numberFmt = new Intl.NumberFormat("en-US");

interface JobSearchProps {
  selectedId: string | null;
  onSelect: (job: JobSummary) => void;
  initialQuery?: string;
  eyebrow?: string;
  heading?: string;
  /** Unique per instance so radio groups don't collide when rendered twice. */
  name?: string;
  debounceMs?: number;
}

type Status = "loading" | "success" | "error";

export function JobSearch({
  selectedId,
  onSelect,
  initialQuery = "engineer",
  eyebrow = "Step 2",
  heading = "Find a role",
  name = "job-search",
  debounceMs = 350,
}: JobSearchProps) {
  const searchId = useId();
  const headingId = useId();
  const [query, setQuery] = useState(initialQuery);
  const [workplace, setWorkplace] = useState<WorkplaceFilter>("any");
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string>("");
  const [data, setData] = useState<JobListResponse | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<string>("");
  // Show a cold-start hint if the initial load takes unusually long.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (status !== "loading") {
      setSlow(false);
      return;
    }
    const t = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(t);
  }, [status]);
  const debouncedQuery = useDebounce(query, debounceMs);
  const moreController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    moreController.current?.abort();
    setStatus("loading");
    setMoreError("");
    setLoadingMore(false);
    searchJobs({ q: debouncedQuery, page: 0, workplace: workplace === "any" ? null : workplace }, controller.signal)
      .then((res) => {
        setData(res);
        setStatus("success");
      })
      .catch((err: unknown) => {
        if (isAbortError(err)) return;
        setError(friendlyErrorMessage(err));
        setStatus("error");
      });
    return () => controller.abort();
  }, [debouncedQuery, workplace, reloadKey]);

  useEffect(() => () => moreController.current?.abort(), []);

  const loadMore = useCallback(() => {
    if (!data) return;
    const controller = new AbortController();
    moreController.current?.abort();
    moreController.current = controller;
    setLoadingMore(true);
    setMoreError("");
    searchJobs(
      { q: debouncedQuery, page: data.page + 1, workplace: workplace === "any" ? null : workplace },
      controller.signal,
    )
      .then((res) => {
        setData((prev) => {
          if (!prev) return res;
          const seen = new Set(prev.jobs.map((j) => j.id));
          return { ...res, jobs: [...prev.jobs, ...res.jobs.filter((j) => !seen.has(j.id))] };
        });
        setLoadingMore(false);
      })
      .catch((err: unknown) => {
        if (isAbortError(err)) return;
        setMoreError(friendlyErrorMessage(err));
        setLoadingMore(false);
      });
  }, [data, debouncedQuery, workplace]);

  const hasMore = data !== null && data.page < data.total_pages - 1;
  const liveText =
    status === "loading"
      ? "Loading roles…"
      : status === "error"
        ? "Couldn't load roles."
        : data
          ? `${numberFmt.format(data.total)} ${data.total === 1 ? "role matches" : "roles match"}`
          : "";

  return (
    <section aria-labelledby={headingId} className="card p-4">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={headingId} className="mt-0.5 text-[15px] font-semibold">
        {heading}
      </h2>

      <div className="mt-3.5 space-y-2.5">
        <div>
          <label htmlFor={searchId} className="sr-only">
            Search roles
          </label>
          <div className="relative">
            <Search aria-hidden="true" className="text-ink-3 pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
            <input
              id={searchId}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search title, company or skill"
              className="input pl-8"
              autoComplete="off"
              maxLength={120}
            />
          </div>
        </div>
        <Segmented
          legend="Workplace filter"
          hideLegend
          name={`${name}-workplace`}
          value={workplace}
          options={WORKPLACE_FILTERS}
          onChange={setWorkplace}
          size="sm"
        />
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-2">
        <p aria-live="polite" className="text-ink text-[12.5px] font-medium">
          {status === "loading" ? (
            <span className="text-ink-2 inline-flex items-center gap-1.5">
              <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              {liveText}
            </span>
          ) : (
            liveText
          )}
        </p>
        <p className="text-ink-3 font-mono text-[10.5px]">Data: speedrun talent network API</p>
      </div>

      <div className="mt-2">
        {status === "loading" && (
          <div className="space-y-2" data-testid="job-skeletons">
            {slow && (
              <p className="text-ink-2 text-[12.5px]" role="status">
                Waking up the demo server. The first request can take up to a minute on the free tier.
              </p>
            )}
            <JobCardSkeleton />
            <JobCardSkeleton />
            <JobCardSkeleton />
          </div>
        )}

        {status === "error" && (
          <ErrorCard title="Couldn't load roles" message={error} onRetry={() => setReloadKey((k) => k + 1)} />
        )}

        {status === "success" && data && data.jobs.length === 0 && (
          <div className="border-line text-ink-2 rounded-lg border border-dashed px-3 py-6 text-center text-[13px]">
            No roles match — try “design” or “founding”.
          </div>
        )}

        {status === "success" && data && data.jobs.length > 0 && (
          <>
            <ul className="-mx-1 space-y-2 px-1 py-1 lg:max-h-[560px] lg:overflow-y-auto" aria-label="Matching roles">
              {data.jobs.map((job) => (
                <li key={job.id} className="animate-fade-in">
                  <JobCard job={job} selected={job.id === selectedId} onSelect={onSelect} />
                </li>
              ))}
            </ul>
            {moreError && <p role="alert" className="text-bad mt-2 text-[12.5px]">{moreError}</p>}
            {hasMore && (
              <button type="button" className="btn-secondary mt-2.5 w-full" onClick={loadMore} disabled={loadingMore}>
                {loadingMore && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            )}
          </>
        )}
      </div>
    </section>
  );
}
