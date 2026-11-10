import type { LucideIcon } from "lucide-react";
import {
  Ban,
  CircleCheck,
  CircleDashed,
  CircleHelp,
  CircleX,
  CodeXml,
  Info,
  ShieldCheck,
  ShieldQuestion,
  ShieldX,
  TriangleAlert,
} from "lucide-react";
import type {
  AuthorizationLabel,
  ClaimCategory,
  ClarityStatus,
  Extractor,
  FindingStatus,
  LlmStatus,
  SectionStatus,
  TechnicalStatus,
} from "./types";

export type Tone = "ok" | "bad" | "warn" | "neutral" | "missing";

export interface StatusMeta {
  tone: Tone;
  label: string;
  icon: LucideIcon;
}

export const SECTION_STATUS: Record<SectionStatus, StatusMeta> = {
  compatible: { tone: "ok", label: "Compatible", icon: CircleCheck },
  conflict: { tone: "bad", label: "Conflict", icon: CircleX },
  needs_clarification: { tone: "warn", label: "Needs clarification", icon: TriangleAlert },
  unknown: { tone: "neutral", label: "Unknown", icon: CircleHelp },
};

export const AUTH_LABEL: Record<AuthorizationLabel, StatusMeta> = {
  explicitly_supported: { tone: "ok", label: "Explicitly supported", icon: ShieldCheck },
  explicitly_restricted: { tone: "bad", label: "Explicitly restricted", icon: ShieldX },
  not_specified: { tone: "neutral", label: "Not specified", icon: ShieldQuestion },
  needs_clarification: { tone: "warn", label: "Needs clarification", icon: TriangleAlert },
};

export const FINDING_STATUS: Record<FindingStatus, StatusMeta> = {
  agreement: { tone: "ok", label: "Agreement", icon: CircleCheck },
  conflict: { tone: "bad", label: "Conflict", icon: CircleX },
  unknown: { tone: "neutral", label: "Unknown", icon: CircleHelp },
  caution: { tone: "warn", label: "Caution", icon: TriangleAlert },
};

export const TECHNICAL_STATUS: Record<TechnicalStatus, StatusMeta> = {
  assessed: { tone: "neutral", label: "Supporting info", icon: CodeXml },
  needs_skills: { tone: "neutral", label: "Add skills to compare", icon: Info },
  no_requirements_found: { tone: "neutral", label: "No requirements found", icon: Ban },
};

export const CLARITY_STATUS: Record<ClarityStatus, StatusMeta> = {
  clear: { tone: "ok", label: "Clear", icon: CircleCheck },
  partial: { tone: "warn", label: "Partial", icon: TriangleAlert },
  missing: { tone: "missing", label: "Missing", icon: CircleDashed },
};

export const CATEGORY_LABEL: Record<ClaimCategory, string> = {
  work_arrangement: "Work arrangement",
  job_location: "Job location",
  geographic_restriction: "Geographic restriction",
  sponsorship_policy: "Sponsorship policy",
  relocation_requirement: "Relocation",
  employment_type: "Employment type",
  technical_requirement: "Technical requirement",
};

export const EXTRACTOR_LABEL: Record<Extractor, string> = {
  metadata: "metadata",
  rules: "rules",
  llm: "AI",
};

export const LLM_STATUS_TEXT: Record<LlmStatus, string> = {
  disabled: "AI extraction: off — deterministic rules only",
  ok: "AI extraction: on — every AI claim was checked against an exact quote",
  failed: "AI extraction: unavailable this run — deterministic rules only",
  skipped: "AI extraction: skipped — deterministic rules only",
};

/** "full_time" / "Full-time" → "Full time" */
export function humanize(value: string | null | undefined): string {
  if (!value) return "";
  const s = value
    .replace(/([a-z])([A-Z])/g, "$1 $2") // FullTime -> Full Time
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function confidenceText(c: number): string {
  const level = c >= 0.85 ? "High" : c >= 0.6 ? "Medium" : "Low";
  return `${level} · ${c.toFixed(2)}`;
}

/** Canonical snake_case values ("not_offered") are humanized; free text is shown verbatim. */
export function displayValue(value: string): string {
  return /^[a-z]+(_[a-z]+)*$/.test(value) ? humanize(value) : value;
}
