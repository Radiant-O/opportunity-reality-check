import { describe, expect, it, vi } from "vitest";
import { API_BASE_URL, ApiError, analyze, friendlyErrorMessage, searchJobs } from "./api";
import { analysisResponse, jobListPage0 } from "./test/fixtures";
import { jsonResponse, mockFetch } from "./test/utils";

describe("api", () => {
  it("builds the jobs query string and returns typed data", async () => {
    const fetchMock = mockFetch(() => jsonResponse(jobListPage0));
    const res = await searchJobs({ q: " engineer ", page: 2, workplace: "remote" });
    expect(res.total).toBe(2477);
    const url = new URL(String(fetchMock.mock.calls[0]![0]));
    expect(url.origin + url.pathname).toBe(`${API_BASE_URL}/api/jobs`);
    expect(url.searchParams.get("q")).toBe("engineer");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("workplace")).toBe("remote");
  });

  it("POSTs JSON to /api/analyze", async () => {
    const fetchMock = mockFetch(() => jsonResponse(analysisResponse));
    await analyze({ job_id: "job_8f2c1a9e", preferences: { country: "Nigeria", sponsorship: "yes" } });
    const init = fetchMock.mock.calls[0]![1]!;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ job_id: "job_8f2c1a9e", preferences: { country: "Nigeria", sponsorship: "yes" } });
  });

  it.each([
    [429, "You're going a bit fast — try again in a minute."],
    [502, "The speedrun API didn't respond. Try again."],
    [504, "The speedrun API didn't respond. Try again."],
    [404, "This listing is no longer available."],
  ])("maps HTTP %i to an ApiError with a friendly message", async (status, friendly) => {
    mockFetch(() => jsonResponse({ detail: "upstream said no" }, status));
    const err = await searchJobs({ q: "x" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(status);
    expect((err as ApiError).message).toBe("upstream said no");
    expect(friendlyErrorMessage(err)).toBe(friendly);
  });

  it("flattens FastAPI 422 validation details", async () => {
    mockFetch(() => jsonResponse({ detail: [{ loc: ["body", "job_id"], msg: "String too short", type: "string_too_short" }] }, 422));
    const err = (await analyze({ job_id: "x" }).catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(422);
    expect(err.message).toBe("String too short");
  });

  it("maps network failures to status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = (await searchJobs({}).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(friendlyErrorMessage(err)).toMatch(/couldn't reach/i);
  });

  it("keeps status text when the error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => {
          throw new SyntaxError("bad json");
        },
      }),
    );
    const err = (await searchJobs({}).catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(500);
    expect(err.message).toBe("Internal Server Error");
  });

  it("rethrows aborts as AbortError, not ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        });
      }),
    );
    const controller = new AbortController();
    const p = searchJobs({}, controller.signal);
    controller.abort();
    const err = await p.catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DOMException);
    expect((err as DOMException).name).toBe("AbortError");
  });
});
