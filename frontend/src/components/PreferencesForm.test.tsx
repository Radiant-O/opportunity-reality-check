import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, PreferencesForm, toCandidatePreferences, type Preferences } from "./PreferencesForm";

let latest: Preferences = DEFAULT_PREFERENCES;

function Harness() {
  const [value, setValue] = useState<Preferences>(DEFAULT_PREFERENCES);
  latest = value;
  return <PreferencesForm value={value} onChange={setValue} />;
}

describe("PreferencesForm", () => {
  it("starts with the contract defaults", () => {
    render(<Harness />);
    expect(screen.getByRole("radio", { name: "Flexible" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Depends" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Not sure" })).toBeChecked();
    expect(screen.getByText("Kept in this tab only. No account, nothing stored.")).toBeInTheDocument();
  });

  it("updates country and segmented values", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByLabelText("Country of residence"), "Nigeria");
    await user.click(screen.getByRole("radio", { name: "Remote" }));
    const relocation = screen.getByRole("group", { name: "Open to relocation" });
    await user.click(relocation.querySelector('input[value="no"]')!);
    const sponsorship = screen.getByRole("group", { name: "Need employer visa sponsorship" });
    await user.click(sponsorship.querySelector('input[value="yes"]')!);

    expect(latest).toMatchObject({ country: "Nigeria", work_arrangement: "remote", relocation: "no", sponsorship: "yes" });
    expect(sponsorship).toHaveAccessibleDescription(/We only report what the listing says/);
  });

  it("adds skills with Enter and comma, removes with Backspace and the remove button", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByLabelText("Skills (optional)");

    await user.type(input, "TypeScript{Enter}");
    await user.type(input, "React,");
    await user.type(input, "python{Enter}");
    await user.type(input, "react{Enter}"); // duplicate (case-insensitive) is ignored
    expect(latest.skills).toEqual(["TypeScript", "React", "python"]);

    await user.click(screen.getByRole("button", { name: "Remove React" }));
    expect(latest.skills).toEqual(["TypeScript", "python"]);

    await user.click(input);
    await user.keyboard("{Backspace}");
    expect(latest.skills).toEqual(["TypeScript"]);
    expect(screen.getByText(/1\/20/)).toBeInTheDocument();
  });

  it("normalizes to the request payload", () => {
    expect(toCandidatePreferences({ ...DEFAULT_PREFERENCES, country: "  " })).toEqual({
      country: null,
      work_arrangement: "flexible",
      relocation: "conditional",
      sponsorship: "unsure",
      skills: [],
    });
  });
});
