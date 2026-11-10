/**
 * API contract — mirrors backend/app/models.py exactly.
 * Keep field names, optionality and literal unions in sync with the backend.
 */

// ---------------------------------------------------------------------------
// Candidate preferences (never persisted, never logged)
// ---------------------------------------------------------------------------

export type WorkPreference = "remote" | "hybrid" | "onsite" | "flexible";
export type RelocationPreference = "yes" | "no" | "conditional";
export type SponsorshipNeed = "yes" | "no" | "unsure";

export interface CandidatePreferences {
  /** Current country of residence (free text, max 64 chars). */
  country?: string | null;
  work_arrangement?: WorkPreference;
  relocation?: RelocationPreference;
  sponsorship?: SponsorshipNeed;
  /** Max 20 items, each trimmed to 40 chars and de-duplicated server-side. */
  skills?: string[];
}

// ---------------------------------------------------------------------------
// Jobs (normalized from the speedrun API)
// ---------------------------------------------------------------------------

export type WorkplaceType = "remote" | "hybrid" | "onsite";

export interface JobSummary {
  id: string;
  title: string;
  company: string;
  company_url?: string | null;
  location?: string | null;
  workplace_type?: WorkplaceType | null;
  workplace_type_raw?: string | null;
  employment_type?: string | null;
  function?: string | null;
  seniority?: string | null;
  remote?: boolean;
  published_at?: string | null;
  /** Canonical speedrun job URL. Always link users here. */
  url: string;
}

export interface JobDetail extends JobSummary {
  status?: "open" | "closed";
  apply_url?: string | null;
  apply_kind?: "onsite" | "external" | null;
  comp_summary?: string | null;
  description_text?: string | null;
}

export interface JobListResponse {
  jobs: JobSummary[];
  total: number;
  page: number;
  total_pages: number;
  query?: string | null;
  attribution?: string;
}

// ---------------------------------------------------------------------------
// Extraction
// ---------------------------------------------------------------------------

export type ClaimCategory =
  | "work_arrangement"
  | "job_location"
  | "geographic_restriction"
  | "sponsorship_policy"
  | "relocation_requirement"
  | "employment_type"
  | "technical_requirement";

export const CLAIM_CATEGORIES: readonly ClaimCategory[] = [
  "work_arrangement",
  "job_location",
  "geographic_restriction",
  "sponsorship_policy",
  "relocation_requirement",
  "employment_type",
  "technical_requirement",
] as const;

export type EvidenceSource =
  | "description"
  | "metadata.location"
  | "metadata.workplace_type"
  | "metadata.employment_type"
  | "metadata.remote";

export type VerificationStatus = "verified" | "rejected";
export type Extractor = "metadata" | "rules" | "llm";

export interface Claim {
  id: string;
  category: ClaimCategory;
  value: string;
  evidence_text: string;
  evidence_source: EvidenceSource;
  /** 0.0 – 1.0 */
  confidence: number;
  verification_status?: VerificationStatus;
  extractor: Extractor;
  rejection_reason?: string | null;
}

export type LlmStatus = "disabled" | "ok" | "failed" | "skipped";

export interface ExtractionReport {
  claims: Claim[];
  rejected_claims?: Claim[];
  unknown_categories?: ClaimCategory[];
  llm_status?: LlmStatus;
  /** Listing contains text addressed to AI tools; AI-extracted claims were discarded. */
  injection_detected?: boolean;
  description_chars?: number;
  description_truncated?: boolean;
}

// ---------------------------------------------------------------------------
// Analysis output
// ---------------------------------------------------------------------------

export type FindingStatus = "agreement" | "conflict" | "unknown" | "caution";

export interface Finding {
  rule_id: string;
  status: FindingStatus;
  title: string;
  explanation: string;
  evidence_claim_ids?: string[];
}

export type SectionStatus = "compatible" | "conflict" | "needs_clarification" | "unknown";

export interface LocationSection {
  status: SectionStatus;
  headline: string;
  job_location: string | null;
  job_country: string | null;
  work_arrangement: WorkplaceType | null;
  findings: Finding[];
}

export type AuthorizationLabel =
  | "explicitly_supported"
  | "explicitly_restricted"
  | "not_specified"
  | "needs_clarification";

export interface AuthorizationSection {
  label: AuthorizationLabel;
  headline: string;
  findings: Finding[];
  note: string;
}

export interface SkillMatch {
  skill: string;
  evidence_claim_id?: string | null;
}

export type TechnicalStatus = "needs_skills" | "assessed" | "no_requirements_found";

export interface TechnicalSection {
  status: TechnicalStatus;
  headline: string;
  matched?: SkillMatch[];
  listed_not_provided?: SkillMatch[];
  provided_not_listed?: string[];
  note: string;
}

export type Priority = "high" | "medium" | "low";

export interface NextStep {
  id: string;
  text: string;
  reason: string;
  priority: Priority;
}

export interface AnalysisResponse {
  job: JobDetail;
  extraction: ExtractionReport;
  technical: TechnicalSection;
  location: LocationSection;
  authorization: AuthorizationSection;
  assessment: string;
  next_steps: NextStep[];
  draft_inquiry: string;
  disclaimer: string;
}

export interface AnalyzeRequest {
  /** 6–160 chars */
  job_id: string;
  preferences?: CandidatePreferences;
}

// ---------------------------------------------------------------------------
// Listing clarity (founder-facing)
// ---------------------------------------------------------------------------

export interface ClarityRequest {
  job_id?: string | null;
  /** Max 15000 chars */
  description_text?: string | null;
  location?: string | null;
  workplace_type?: string | null;
  employment_type?: string | null;
}

export type ClarityStatus = "clear" | "partial" | "missing";

export type ClarityDimension =
  | "location"
  | "work_arrangement"
  | "relocation"
  | "sponsorship"
  | "employment_type";

export interface ClarityItem {
  dimension: ClarityDimension;
  label: string;
  status: ClarityStatus;
  detail: string;
  evidence_claim_ids?: string[];
  suggestion?: string | null;
}

export interface ClarityResponse {
  items: ClarityItem[];
  clear_count: number;
  total: number;
  extraction: ExtractionReport;
  job?: JobSummary | null;
  note: string;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  detail: string | unknown;
}
