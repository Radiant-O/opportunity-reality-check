import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { analysisResponse, jobDetail, jobSummaries } from "../test/fixtures";
import { jsonResponse, mockFetch } from "../test/utils";
import { AnalysisPanel } from "./AnalysisPanel";
import { DEFAULT_PREFERENCES, type Preferences } from "./PreferencesForm";

const prefs: Preferences = {
  country: "Nigeria",
  work_arrangement: "remote",
  relocation: "no",
  sponsorship: "yes",
  skills: ["Python", "AWS", "React"],
};

function routes(analyzeStatus = 200) {
  return mockFetch((url) => {
    if (url.pathname === "/api/analyze") {
      return analyzeStatus === 200 ? jsonResponse(analysisResponse) : jsonResponse({ detail: "nope" }, analyzeStatus);
    }
    if (url.pathname.startsWith("/api/jobs/")) return jsonResponse(jobDetail);
    throw new Error(`Unexpected request ${url.href}`);
  });
}

describe("AnalysisPanel", () => {
  it("shows the explainer and status legend before a job is selected", () => {
    render(<AnalysisPanel job={null} preferences={DEFAULT_PREFERENCES} />);
    expect(screen.getByRole("heading", { name: "Pick a role to reality-check" })).toBeInTheDocument();
    for (const label of ["Supported", "Restricted", "Not specified", "Needs clarification", "Agreement", "Conflict", "Unknown", "Caution"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("requires a click, sends preferences, and renders the full result", async () => {
    const user = userEvent.setup();
    const fetchMock = routes();
    render(<AnalysisPanel job={jobSummaries[0]!} preferences={prefs} />);

    // Header + detail enrichment, but no analysis yet.
    expect(screen.getByRole("heading", { name: "Founding Backend Engineer" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Apply on official page/ })).toHaveAttribute("href", jobDetail.apply_url);
    expect(screen.getByText(jobDetail.comp_summary!)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/api/analyze"))).toBe(false);

    await user.click(screen.getByRole("button", { name: "Run reality check" }));

    const analyzeCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/api/analyze"))!;
    expect(JSON.parse(String(analyzeCall[1]!.body))).toEqual({
      job_id: "job_8f2c1a9e",
      preferences: { country: "Nigeria", work_arrangement: "remote", relocation: "no", sponsorship: "yes", skills: ["Python", "AWS", "React"] },
    });

    // 1. Assessment
    expect(await screen.findByText(analysisResponse.assessment)).toBeInTheDocument();

    // 2. Three sections with status badges (icon + text)
    const location = screen.getByRole("region", { name: "Location & work arrangement" });
    expect(within(location).getAllByText("Conflict").length).toBeGreaterThan(0);
    expect(within(location).getByText(analysisResponse.location.headline)).toBeInTheDocument();
    expect(within(location).getByText("Hybrid role, you prefer remote")).toBeInTheDocument();

    const auth = screen.getByRole("region", { name: "Work authorization & sponsorship" });
    expect(within(auth).getByText("Explicitly restricted")).toBeInTheDocument();
    expect(within(auth).getByText(analysisResponse.authorization.note)).toBeInTheDocument();
    // Evidence lookup by claim id
    expect(within(auth).getByText("Evidence (2)")).toBeInTheDocument();
    expect(within(auth).getByText("“we are unable to sponsor visas at this time”")).toBeInTheDocument();
    expect(within(auth).getByText("“Candidates must be authorized to work in the United States”")).toBeInTheDocument();

    const tech = screen.getByRole("region", { name: "Technical alignment" });
    expect(within(tech).getByText("Supporting info")).toBeInTheDocument();
    expect(within(within(tech).getByRole("list", { name: "Matched — listed and provided" })).getByText("Python")).toBeInTheDocument();
    expect(within(tech).getByText("PostgreSQL")).toBeInTheDocument();
    expect(within(tech).getByText("React")).toBeInTheDocument();
    expect(within(tech).getByText(/not a hiring decision/i)).toBeInTheDocument();

    // 3. Next steps
    const step = screen.getByRole("checkbox", { name: "Decide whether hybrid in San Francisco is acceptable" });
    expect(step).not.toBeChecked();
    await user.click(step);
    expect(step).toBeChecked();
    expect(screen.getByText("high priority")).toBeInTheDocument();

    // 5. Evidence & uncertainty
    expect(screen.getByText("Evidence & uncertainty")).toBeInTheDocument();
    expect(screen.getByText("Not stated in listing")).toBeInTheDocument();
    expect(screen.getAllByText("Relocation").length).toBeGreaterThan(0);
    expect(screen.getByText("Geographic restriction")).toBeInTheDocument();
    expect(screen.getByText("Discarded — quote not found in listing")).toBeInTheDocument();
    expect(screen.getByText("Reason: Quoted text does not appear in the listing.")).toBeInTheDocument();
    expect(screen.getAllByTitle("Confidence is not proof").length).toBe(analysisResponse.extraction.claims.length);
    expect(screen.getByText(/AI extraction: on/)).toBeInTheDocument();

    // 6. Disclaimer
    expect(screen.getByText(analysisResponse.disclaimer)).toBeInTheDocument();
  });

  it("copies the draft inquiry and announces it", async () => {
    const user = userEvent.setup();
    routes();
    render(<AnalysisPanel job={jobSummaries[0]!} preferences={prefs} />);
    await user.click(screen.getByRole("button", { name: "Run reality check" }));
    const textarea = await screen.findByLabelText("Message to the employer");
    expect(textarea).toHaveAttribute("readonly");
    expect(textarea).toHaveValue(analysisResponse.draft_inquiry);

    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
    await expect(navigator.clipboard.readText()).resolves.toBe(analysisResponse.draft_inquiry);
  });

  it("shows a re-run notice when preferences change after a result", async () => {
    const user = userEvent.setup();
    routes();
    const { rerender } = render(<AnalysisPanel job={jobSummaries[0]!} preferences={prefs} />);
    await user.click(screen.getByRole("button", { name: "Run reality check" }));
    await screen.findByText(analysisResponse.assessment);
    expect(screen.queryByText(/Preferences changed/)).not.toBeInTheDocument();

    rerender(<AnalysisPanel job={jobSummaries[0]!} preferences={{ ...prefs, sponsorship: "no" }} />);
    expect(screen.getByText("Preferences changed — re-run")).toBeInTheDocument();
  });

  it.each([
    [429, "You're going a bit fast — try again in a minute."],
    [502, "The speedrun API didn't respond. Try again."],
    [504, "The speedrun API didn't respond. Try again."],
    [404, "This listing is no longer available."],
  ])("renders an inline error for HTTP %i with retry", async (status, message) => {
    const user = userEvent.setup();
    const fetchMock = routes(status);
    render(<AnalysisPanel job={jobSummaries[0]!} preferences={prefs} />);
    await user.click(screen.getByRole("button", { name: "Run reality check" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Reality check failed");
    expect(alert).toHaveTextContent(message);

    const before = fetchMock.mock.calls.filter(([u]) => String(u).includes("/api/analyze")).length;
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes("/api/analyze")).length).toBe(before + 1);
  });
});
