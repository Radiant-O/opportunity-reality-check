import { useId } from "react";
import { Lock } from "lucide-react";
import type { CandidatePreferences, RelocationPreference, SponsorshipNeed, WorkPreference } from "../types";
import { Segmented } from "./Segmented";
import { SkillsInput } from "./SkillsInput";

export interface Preferences {
  country: string;
  work_arrangement: WorkPreference;
  relocation: RelocationPreference;
  sponsorship: SponsorshipNeed;
  skills: string[];
}

export const DEFAULT_PREFERENCES: Preferences = {
  country: "",
  work_arrangement: "flexible",
  relocation: "conditional",
  sponsorship: "unsure",
  skills: [],
};

/** Normalize UI state into the request payload. */
export function toCandidatePreferences(p: Preferences): CandidatePreferences {
  const country = p.country.trim();
  return {
    country: country ? country.slice(0, 64) : null,
    work_arrangement: p.work_arrangement,
    relocation: p.relocation,
    sponsorship: p.sponsorship,
    skills: p.skills,
  };
}

export const COUNTRIES = [
  "Argentina", "Australia", "Austria", "Bangladesh", "Belgium", "Brazil", "Bulgaria", "Canada", "Chile", "China",
  "Colombia", "Czech Republic", "Denmark", "Egypt", "Estonia", "Ethiopia", "Finland", "France", "Germany", "Ghana",
  "Greece", "Hong Kong", "Hungary", "India", "Indonesia", "Ireland", "Israel", "Italy", "Japan", "Kenya",
  "Malaysia", "Mexico", "Morocco", "Netherlands", "New Zealand", "Nigeria", "Norway", "Pakistan", "Peru", "Philippines",
  "Poland", "Portugal", "Romania", "Rwanda", "Saudi Arabia", "Serbia", "Singapore", "South Africa", "South Korea", "Spain",
  "Sweden", "Switzerland", "Taiwan", "Thailand", "Turkey", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom",
  "United States", "Uruguay", "Vietnam",
] as const;

const WORK_OPTIONS = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "Onsite" },
  { value: "flexible", label: "Flexible" },
] as const;

const RELOCATION_OPTIONS = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "conditional", label: "Depends" },
] as const;

const SPONSORSHIP_OPTIONS = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "unsure", label: "Not sure" },
] as const;

interface PreferencesFormProps {
  value: Preferences;
  onChange: (next: Preferences) => void;
}

export function PreferencesForm({ value, onChange }: PreferencesFormProps) {
  const countryId = useId();
  const listId = useId();
  const set = <K extends keyof Preferences>(key: K, v: Preferences[K]) => onChange({ ...value, [key]: v });

  return (
    <section aria-labelledby="prefs-title" className="card p-4">
      <p className="eyebrow">Step 1</p>
      <h2 id="prefs-title" className="mt-0.5 text-[15px] font-semibold">
        Your situation
      </h2>
      <form className="mt-3.5 space-y-3.5" onSubmit={(e) => e.preventDefault()} noValidate>
        <div>
          <label htmlFor={countryId} className="label">
            Country of residence
          </label>
          <input
            id={countryId}
            type="text"
            list={listId}
            maxLength={64}
            autoComplete="country-name"
            placeholder="e.g. Nigeria"
            value={value.country}
            onChange={(e) => set("country", e.target.value)}
            className="input"
          />
          <datalist id={listId}>
            {COUNTRIES.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </div>
        <Segmented
          legend="Preferred work arrangement"
          name="work_arrangement"
          value={value.work_arrangement}
          options={WORK_OPTIONS}
          onChange={(v) => set("work_arrangement", v)}
          size="sm"
        />
        <Segmented
          legend="Open to relocation"
          name="relocation"
          value={value.relocation}
          options={RELOCATION_OPTIONS}
          onChange={(v) => set("relocation", v)}
        />
        <Segmented
          legend="Need employer visa sponsorship"
          name="sponsorship"
          value={value.sponsorship}
          options={SPONSORSHIP_OPTIONS}
          onChange={(v) => set("sponsorship", v)}
          helper="Sponsorship depends on the destination country and your legal status. We only report what the listing says."
        />
        <SkillsInput value={value.skills} onChange={(v) => set("skills", v)} />
      </form>
      <p className="text-ink-2 border-line mt-4 flex items-center gap-1.5 border-t pt-3 text-[12px]">
        <Lock aria-hidden="true" className="size-3.5 shrink-0" />
        Kept in this tab only. No account, nothing stored.
      </p>
    </section>
  );
}
