import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App";
import { jobDetail, jobListPage0 } from "./test/fixtures";
import { jsonResponse, mockFetch } from "./test/utils";

describe("App", () => {
  it("renders the shell, disclaims affiliation, and switches modes with the keyboard", async () => {
    const user = userEvent.setup();
    mockFetch((url) => (url.pathname === "/api/jobs" ? jsonResponse(jobListPage0) : jsonResponse(jobDetail)));
    render(<App />);

    expect(screen.getAllByText(/not affiliated with a16z speedrun/i).length).toBeGreaterThan(0);
    expect(await screen.findByText("2,477 roles match")).toBeInTheDocument();

    const candidateTab = screen.getByRole("tab", { name: /Candidate check/ });
    expect(candidateTab).toHaveAttribute("aria-selected", "true");
    candidateTab.focus();
    await user.keyboard("{ArrowRight}");
    const clarityTab = screen.getByRole("tab", { name: /Listing Clarity Check/ });
    expect(clarityTab).toHaveAttribute("aria-selected", "true");
    expect(clarityTab).toHaveFocus();
    expect(screen.getByRole("tabpanel", { name: /Listing Clarity Check/ })).toBeVisible();
  });

  it("selecting a role shows the analysis header without running analysis", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch((url) => (url.pathname === "/api/jobs" ? jsonResponse(jobListPage0) : jsonResponse(jobDetail)));
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /Founding Backend Engineer/ }));
    expect(screen.getByRole("button", { name: "Run reality check" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/api/analyze"))).toBe(false);
  });
});
