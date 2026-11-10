import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { emptyJobList, jobListPage0, jobListPage1 } from "../test/fixtures";
import { deferred, jsonResponse, mockFetch } from "../test/utils";
import { JobSearch } from "./JobSearch";

describe("JobSearch", () => {
  it("shows skeletons while loading, then the results with total count", async () => {
    const pending = deferred<Response>();
    const fetchMock = mockFetch(() => pending.promise);
    render(<JobSearch selectedId={null} onSelect={() => {}} />);

    expect(screen.getByTestId("job-skeletons")).toBeInTheDocument();
    expect(screen.getByText("Loading roles…")).toBeInTheDocument();
    expect(new URL(String(fetchMock.mock.calls[0]![0])).searchParams.get("q")).toBe("engineer");

    pending.resolve(jsonResponse(jobListPage0));
    expect(await screen.findByText("2,477 roles match")).toBeInTheDocument();
    expect(screen.queryByTestId("job-skeletons")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Founding Backend Engineer/ })).toHaveAttribute("aria-pressed", "false");
    const links = screen.getAllByRole("link", { name: /View on speedrun/ });
    expect(links[0]).toHaveAttribute("href", "https://speedrun-talent-network.com/jobs/job_8f2c1a9e");
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(links[0]).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("Data: speedrun talent network API")).toBeInTheDocument();
  });

  it("selects a job and marks it pressed", async () => {
    mockFetch(() => jsonResponse(jobListPage0));
    const onSelect = vi.fn();
    const { rerender } = render(<JobSearch selectedId={null} onSelect={onSelect} />);
    const card = await screen.findByRole("button", { name: /Senior Frontend Engineer/ });
    await userEvent.click(card);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "job_3b7d55c0" }));
    rerender(<JobSearch selectedId="job_3b7d55c0" onSelect={onSelect} />);
    expect(screen.getByRole("button", { name: /Senior Frontend Engineer/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the empty state", async () => {
    mockFetch(() => jsonResponse(emptyJobList));
    render(<JobSearch selectedId={null} onSelect={() => {}} />);
    expect(await screen.findByText(/No roles match — try “design” or “founding”/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("shows an error with retry that refetches", async () => {
    let calls = 0;
    mockFetch(() => {
      calls += 1;
      return calls === 1 ? jsonResponse({ detail: "upstream down" }, 502) : jsonResponse(jobListPage0);
    });
    render(<JobSearch selectedId={null} onSelect={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The speedrun API didn't respond. Try again.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("2,477 roles match")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("filters by workplace and loads more pages", async () => {
    const fetchMock = mockFetch((url) => (url.searchParams.get("page") === "1" ? jsonResponse(jobListPage1) : jsonResponse(jobListPage0)));
    render(<JobSearch selectedId={null} onSelect={() => {}} />);
    await screen.findByText("2,477 roles match");

    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByRole("button", { name: /Machine Learning Engineer/ })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Engineer/ }).filter((b) => b.hasAttribute("aria-pressed"))).toHaveLength(3);

    await userEvent.click(screen.getByRole("radio", { name: "Remote" }));
    await waitFor(() => {
      const last = new URL(String(fetchMock.mock.calls.at(-1)![0]));
      expect(last.searchParams.get("workplace")).toBe("remote");
      expect(last.searchParams.get("page")).toBe("0");
    });
  });

  it("debounces typing before searching", async () => {
    const fetchMock = mockFetch(() => jsonResponse(jobListPage0));
    render(<JobSearch selectedId={null} onSelect={() => {}} debounceMs={50} />);
    await screen.findByText("2,477 roles match");
    const input = screen.getByRole("searchbox", { name: "Search roles" });
    await userEvent.clear(input);
    await userEvent.type(input, "design");
    await waitFor(() => {
      expect(new URL(String(fetchMock.mock.calls.at(-1)![0])).searchParams.get("q")).toBe("design");
    });
    // initial + one debounced search (clear → "" may also fire if typing paused, but never one per keystroke)
    expect(fetchMock.mock.calls.length).toBeLessThanOrEqual(3);
  });
});
