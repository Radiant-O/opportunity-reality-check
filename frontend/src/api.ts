import type {
  AnalysisResponse,
  AnalyzeRequest,
  ClarityRequest,
  ClarityResponse,
  JobDetail,
  JobListResponse,
  WorkplaceType,
} from "./types";

export const API_BASE_URL: string = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export const REQUEST_TIMEOUT_MS = 30_000;

/** Typed error for every failed request. `status` is 0 for network errors and 408 for client timeouts. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** Human-friendly, status-specific message for display. */
export function friendlyErrorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Something went wrong. Try again.";
  }
  switch (err.status) {
    case 429:
      return "You're going a bit fast — try again in a minute.";
    case 502:
    case 504:
      return "The speedrun API didn't respond. Try again.";
    case 404:
      return "This listing is no longer available.";
    case 408:
      return "The request took too long. Try again.";
    case 0:
      return "Couldn't reach the analysis server. Check your connection and try again.";
    case 422:
      return err.message || "Some of the details sent weren't valid.";
    default:
      return err.message || "Something went wrong. Try again.";
  }
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ loc, msg, type }, ...]
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : null))
      .filter((m): m is string => Boolean(m));
    if (msgs.length) return msgs.join("; ");
  }
  return null;
}

async function parseError(res: Response): Promise<ApiError> {
  let message = res.statusText || `Request failed (${res.status})`;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      message = detailToMessage((body as { detail: unknown }).detail) ?? message;
    }
  } catch {
    // Non-JSON error body — keep the status text.
  }
  return new ApiError(res.status, message);
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = REQUEST_TIMEOUT_MS } = opts;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onExternalAbort, { once: true });
  }

  try {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (err) {
      if (timedOut) throw new ApiError(408, "Request timed out");
      if (isAbortError(err) || controller.signal.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      throw new ApiError(0, "Network error");
    }
    if (!res.ok) throw await parseError(res);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onExternalAbort);
  }
}

export interface SearchJobsParams {
  q?: string;
  page?: number;
  workplace?: WorkplaceType | null;
}

export function searchJobs(params: SearchJobsParams, signal?: AbortSignal): Promise<JobListResponse> {
  const qs = new URLSearchParams();
  if (params.q?.trim()) qs.set("q", params.q.trim());
  qs.set("page", String(params.page ?? 0));
  if (params.workplace) qs.set("workplace", params.workplace);
  return request<JobListResponse>(`/api/jobs?${qs.toString()}`, { signal });
}

export function getJob(id: string, signal?: AbortSignal): Promise<JobDetail> {
  return request<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`, { signal });
}

export function analyze(body: AnalyzeRequest, signal?: AbortSignal): Promise<AnalysisResponse> {
  return request<AnalysisResponse>("/api/analyze", { method: "POST", body, signal });
}

export function checkClarity(body: ClarityRequest, signal?: AbortSignal): Promise<ClarityResponse> {
  return request<ClarityResponse>("/api/listing-clarity", { method: "POST", body, signal });
}
