import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { clarityResponse, jobListPage0 } from "../test/fixtures";
import { jsonResponse, mockFetch } from "../test/utils";
import { ClarityCheck, SAMPLE_DESCRIPTION } from "./ClarityCheck";

describe("ClarityCheck", () => {
  it("loads the sample, submits, and renders the clarity result", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch((url) => {
      if (url.pathname === "/api/listing-clarity") return jsonResponse(clarityResponse);
      throw new Error(`Unexpected ${url.href}`);
    });
    render(<ClarityCheck />);

    await user.click(screen.getByRole("button", { name: "Load sample description" }));
    expect(screen.getByLabelText("Job description")).toHaveValue(SAMPLE_DESCRIPTION);
    expect(screen.getByText(`${SAMPLE_DESCRIPTION.length.toLocaleString("en-US")} / 15,000`)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Check clarity" }));
    const body = JSON.parse(String(fetchMock.mock.calls[0]![1]!.body));
    expect(body).toEqual({
      description_text: SAMPLE_DESCRIPTION,
      location: "San Francisco, CA",
      workplace_type: "hybrid",
      employment_type: "full_time",
    });

    expect(await screen.findByRole("heading", { name: "2 of 5 essentials are clear" })).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();

    const items = screen.getByRole("heading", { name: "2 of 5 essentials are clear" }).closest("section")!;
    expect(within(items).getAllByText("Clear")).toHaveLength(2);
    expect(within(items).getAllByText("Missing")).toHaveLength(2);
    expect(within(items).getByText("Partial")).toBeInTheDocument();
    expect(within(items).getByText("Visa sponsorship")).toBeInTheDocument();
    expect(within(items).getByText(/We sponsor H-1B visas/)).toBeInTheDocument();
    expect(within(items).getByText("“We work together in our SoMa office 3 days a week”")).toBeInTheDocument();
    expect(screen.getByText(clarityResponse.note)).toBeInTheDocument();
  });

  it("validates empty input without calling the API", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch(() => jsonResponse(clarityResponse));
    render(<ClarityCheck />);
    await user.click(screen.getByRole("button", { name: "Check clarity" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Paste a job description/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("checks a live listing by job id", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch((url) => {
      if (url.pathname === "/api/jobs") return jsonResponse(jobListPage0);
      if (url.pathname === "/api/listing-clarity") return jsonResponse({ ...clarityResponse, job: jobListPage0.jobs[0] });
      throw new Error(`Unexpected ${url.href}`);
    });
    render(<ClarityCheck />);
    await user.click(screen.getByRole("radio", { name: "Use a live listing" }));
    await user.click(await screen.findByRole("button", { name: /Founding Backend Engineer/ }));
    await user.click(screen.getByRole("button", { name: "Check clarity" }));
    expect(await screen.findByText(/Result · Founding Backend Engineer at Northwind Robotics/)).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/api/listing-clarity"))!;
    expect(JSON.parse(String(call[1]!.body))).toEqual({ job_id: "job_8f2c1a9e" });
  });

  it("shows API errors with retry", async () => {
    const user = userEvent.setup();
    mockFetch(() => jsonResponse({ detail: "slow down" }, 429));
    render(<ClarityCheck />);
    await user.click(screen.getByRole("button", { name: "Load sample description" }));
    await user.click(screen.getByRole("button", { name: "Check clarity" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("You're going a bit fast — try again in a minute.");
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
