# Frontend build brief — Opportunity Reality Check

You are building ONLY the `frontend/` directory of this repo. Do not touch `backend/` or anything outside `frontend/`. Do not run git commands (no commit, no branch). Work on Windows (Git Bash / PowerShell available; Node 22, npm).

## Product
"Opportunity Reality Check" — an independent demo that helps job seekers see whether a real job listing from the a16z speedrun talent network is compatible with their location, work-arrangement preference, relocation openness and need for visa sponsorship. It shows what the listing explicitly states (with quoted evidence), what is unknown, conflicts, and next steps. It is a decision-support tool, NOT a chatbot. It is NOT affiliated with speedrun/a16z and must say so in the header/footer ("Independent demo · not affiliated with a16z speedrun"). Results are informational, not legal/immigration advice.

## Stack (required)
Vite + React 18 + TypeScript (strict) + Tailwind CSS v4 (via `@tailwindcss/vite`) + Vitest + React Testing Library + jsdom. No component library, no router, no state library. `lucide-react` for icons is OK. Fonts: "IBM Plex Sans" (UI) and "IBM Plex Mono" (evidence quotes, small labels, ids) from Google Fonts.

`npm run dev`, `npm run build` (tsc -b && vite build), `npm test` (vitest run), `npm run lint` (tsc --noEmit is fine) must all work.

API base URL: `import.meta.env.VITE_API_BASE_URL` (default `http://localhost:8000`). Also add a Vite dev proxy is NOT needed; just use the env var. Provide `frontend/.env.example`.

## Backend API contract (FastAPI; source of truth is `backend/app/models.py` — READ IT and mirror it exactly in `frontend/src/types.ts`)
- `GET /api/jobs?q=<text>&page=<n>&workplace=<remote|hybrid|onsite>` → `JobListResponse`
- `GET /api/jobs/{id}` → `JobDetail`
- `POST /api/analyze` body `AnalyzeRequest {job_id, preferences: CandidatePreferences}` → `AnalysisResponse`
- `POST /api/listing-clarity` body `ClarityRequest` (either `{job_id}` OR `{description_text, location?, workplace_type?, employment_type?}`) → `ClarityResponse`
- Errors: non-2xx JSON `{ "detail": string }` (status 429 = rate limited, 502/504 = upstream speedrun API problem, 404 = job not found, 422 = validation).

## Screens / layout
Single page. Top: slim header (wordmark "Opportunity Reality Check", tagline, "Independent demo" pill, link to speedrun-talent-network.com/jobs). A short landing/hero block with the product promise: "Know what a job listing actually says about location, remote work and visa sponsorship — before you spend hours applying." plus 3 tiny principle chips: "Quotes, not guesses" · "Unknown ≠ No" · "Nothing leaves your browser except the analysis request" (wording can be tightened).

Mode switch (segmented control, keyboard accessible, role="tablist"): **Candidate check** (default) | **Listing Clarity Check** (for founders).

### Candidate check (desktop: 2 columns, ~380px left rail + fluid right; mobile: stacked)
Left rail:
1. **Your situation** compact form card:
   - Country of residence: text input with `<datalist>` of ~60 common countries (Nigeria, United States, India, United Kingdom, Canada, Germany, Brazil, Kenya, Ghana, South Africa, Egypt, Pakistan, Bangladesh, Philippines, Indonesia, Mexico, Argentina, Colombia, France, Spain, Italy, Netherlands, Poland, Ukraine, Turkey, Israel, UAE, Singapore, Japan, South Korea, China, Australia, New Zealand, Ireland, Portugal, Sweden, Switzerland, Vietnam, etc.).
   - Preferred work arrangement: segmented radio (Remote / Hybrid / Onsite / Flexible).
   - Open to relocation: segmented radio (Yes / No / Depends).  values: yes/no/conditional
   - Need employer visa sponsorship: segmented radio (Yes / No / Not sure). values yes/no/unsure. Helper text: "Sponsorship depends on the destination country and your legal status. We only report what the listing says."
   - Skills (optional): tag input — type + Enter/comma adds chip, Backspace removes last, max 20, chips removable with a button that has an aria-label.
   - Small privacy line: "Kept in this tab only. No account, nothing stored." Preferences live in React state only (NO localStorage).
2. **Find a role** card: search input (debounced 350ms) + workplace filter chips (Any/Remote/Hybrid/Onsite), results list of compact job cards: title (bold), company, location, workplace badge, "View on speedrun ↗" external link (the `url` field, target=_blank rel=noopener noreferrer). Clicking a card (it's a button/radio-like selectable item, keyboard accessible, aria-pressed or aria-selected) selects it. Show "Load more" when page < total_pages-1. Initial query on load: "engineer". Show total count ("2,477 roles match") and attribution "Data: speedrun talent network API".
   States: loading skeletons, empty ("No roles match — try 'design' or 'founding'"), error with retry button.

Right panel (**Analysis**):
- Empty state before a job is selected: friendly illustration-free explainer of the 3 sections + an "example" of status legend (Supported / Restricted / Not specified / Needs clarification; Agreement / Conflict / Unknown / Caution).
- When a job is selected: job header (title, company, location, workplace, employment type, comp_summary if any, buttons: "Open original listing ↗" (job.url) and "Apply on official page ↗" (apply_url if present)). A primary "Run reality check" button calls POST /api/analyze with current preferences. Also auto-run is NOT desired (cost); require the click. If preferences change after a result, show a subtle "Preferences changed — re-run" notice.
- Loading: skeleton with step text ("Fetching full listing… Extracting statements… Checking evidence… Applying rules…") — just cosmetic cycling is OK.
- Result layout, in this order:
  1. **Assessment** banner: `assessment` string, plain language.
  2. Three section cards in a responsive grid/stack, each with a clear status badge and headline:
     - **Location & work arrangement** (`location.status`: compatible=green "Compatible", conflict=red "Conflict", needs_clarification=amber "Needs clarification", unknown=gray "Unknown"), list `findings` each with status icon + title + explanation + "Evidence" disclosure that shows the quoted claim(s) referenced by `evidence_claim_ids` (look them up in `extraction.claims`).
     - **Work authorization & sponsorship** (`authorization.label`: explicitly_supported=green "Explicitly supported", explicitly_restricted=red "Explicitly restricted", not_specified=gray "Not specified", needs_clarification=amber "Needs clarification"), findings, plus `authorization.note` in small text.
     - **Technical alignment** (`technical.status`), matched skills as green chips, `listed_not_provided` as neutral chips, `provided_not_listed` as dashed chips, `note`. Make clear it's supporting info, not a hiring decision.
  3. **Next steps** checklist (`next_steps`, checkboxes local-only, priority shown as a small label).
  4. **Draft inquiry** (`draft_inquiry`) in a read-only textarea with a "Copy" button (navigator.clipboard, show "Copied" for 2s, aria-live). Note: "We never contact employers. Edit before sending."
  5. **Evidence & uncertainty** disclosure (collapsed by default): table/list of all `extraction.claims` grouped by category, each with value, quoted `evidence_text` in mono with a left border, source (`evidence_source`), extractor badge (metadata/rules/llm), confidence shown as text (not a bar) with tooltip "Confidence is not proof"; then `extraction.unknown_categories` listed as "Not stated in listing"; then `extraction.rejected_claims` (if any) as "Discarded — quote not found in listing" with reason. Show `llm_status` subtly (e.g. "AI extraction: off — deterministic rules only").
  6. Disclaimer text (`disclaimer`).
- Errors: inline error card with message by status (429 → "You're going a bit fast — try again in a minute."; 502/504 → "The speedrun API didn't respond. Try again."; 404 → "This listing is no longer available.") and retry.

### Listing Clarity Check (founder mode)
Card explaining: "Paste a job description (or pick a live listing) to see which candidate-critical details are clear, partial or missing. We report gaps — we never assume your policy."
Two input options (tabs or radio): "Paste description" (textarea up to 15000 chars with counter + optional location / workplace type select / employment type select) or "Use a live listing" (reuse a small job search picker, or a text input for job id — reusing the JobSearch component is preferred).
Button "Check clarity" → POST /api/listing-clarity. Result: score line "3 of 5 essentials are clear" (no percentages), list of `items` each with status badge (clear green / partial amber / missing gray-red-outline), label, detail, suggestion (if present) styled as a suggestion. Evidence disclosure similar to above. Provide a "Load sample description" button that fills a realistic sample text with a couple of gaps (write your own sample; e.g. hybrid SF role mentioning "3 days a week in office" and no sponsorship statement).

## Visual design
- Developer-focused startup product, high information density, calm. Neutral warm-gray background (e.g. #F7F7F4 / stone), white cards with 1px borders (#E7E5E0), radius 10–12px, very soft shadow at most. Text ink #1C1B19, secondary #5F5B53.
- ONE accent color for interactive/primary elements: deep cobalt `#2448E0` (hover darker). Status colors used ONLY for status: green (#15803D on #ECFDF3), red (#B42318 on #FEF3F2), amber (#B54708 on #FFFAEB), gray (#475467 on #F2F4F7). Each status badge must ALSO have an icon + text (never color alone).
- Typography: Plex Sans 14–15px base, headings 600 weight, tight but readable line-height; small uppercase mono labels (11px, letter-spacing .06em) for section eyebrows; evidence quotes in Plex Mono 12.5px with left border.
- Accessible: visible focus rings (accent), all controls keyboard operable, labels for every input, aria-live for async status, contrast AA, prefers-reduced-motion respected. Responsive down to 360px; no horizontal scroll.
- Subtle motion only (fade/slide 150ms).

## Code organization
`src/api.ts` (fetch wrapper with typed errors `ApiError {status, message}`, AbortController support, timeout 30s), `src/types.ts`, `src/components/*` (Header, Hero, ModeTabs, PreferencesForm, SkillsInput, JobSearch, JobCard, AnalysisPanel, StatusBadge, FindingList, EvidenceList, NextSteps, DraftInquiry, ClarityCheck, ErrorCard, Skeleton), `src/hooks/useDebounce.ts`, `src/App.tsx`. Keep components small and typed.

## Tests (Vitest + RTL, mock `fetch` with vi.fn / vi.stubGlobal — no network)
At least: api error mapping; JobSearch loading → success, empty, error+retry; PreferencesForm changes values & SkillsInput add/remove; AnalysisPanel renders success result with all three sections, status badges text, evidence lookup, unknown categories and rejected claims; copy button; analysis error states (429, 502); ClarityCheck success render. Put a realistic fixture `src/test/fixtures.ts` matching the contract.

## Definition of done
`npm install`, `npm run build`, `npm test` all pass in `frontend/`. Report briefly what you built and the test results. Add `frontend/public/favicon.svg` (simple geometric mark using the accent color) and set `<title>Opportunity Reality Check</title>` plus a meta description.
