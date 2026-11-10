import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { analysisResponse } from "../test/fixtures";
import { EvidenceList } from "./EvidenceList";

describe("EvidenceList", () => {
  it("warns when the listing contains text addressed to AI tools", () => {
    render(<EvidenceList extraction={{ ...analysisResponse.extraction, injection_detected: true }} />);
    expect(screen.getByRole("note")).toHaveTextContent(/addressed to AI tools/);
  });

  it("shows no warning for a normal listing", () => {
    render(<EvidenceList extraction={{ ...analysisResponse.extraction, injection_detected: false }} />);
    expect(screen.queryByText(/addressed to AI tools/)).not.toBeInTheDocument();
  });
});
