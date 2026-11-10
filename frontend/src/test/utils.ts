import { vi } from "vitest";

export interface MockResponseInit {
  status?: number;
  body?: unknown;
}

export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: async () => body,
  } as unknown as Response;
}

type Handler = (url: URL, init: RequestInit | undefined) => Response | Promise<Response>;

/** Stub global fetch with a URL-based handler. Returns the vi.fn for assertions. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    return handler(url, init);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** A promise you can resolve later, for asserting loading states. */
export function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
