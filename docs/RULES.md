# Compatibility rules

All rules are deterministic Python in `backend/app/rules.py`. They read **only verified claims**, meaning claims whose quote was found in the listing (see `backend/app/extraction/validate.py`). Each finding carries a `rule_id`, a status (`agreement`, `conflict`, `unknown`, `caution`) and the ids of the claims that support it.

No rule produces a score, and no rule decides legal eligibility.

## Work arrangement resolution

If the description states an arrangement, the most restrictive one wins (onsite > hybrid > remote), because the text is more specific than the board's workplace label. Otherwise the label is used. If the two disagree, `L0` flags it.

## Location & work arrangement

| Rule | Status | Fires when |
|---|---|---|
| `L0_SOURCE_DISAGREEMENT` | caution | The board label and the description disagree on the arrangement |
| `L1_ARRANGEMENT_UNKNOWN` | unknown | No arrangement stated anywhere |
| `L1_ARRANGEMENT_MATCH` | agreement | Preference is `flexible` or equals the stated arrangement |
| `L1_ARRANGEMENT_CONFLICT` | conflict | Candidate wants remote and the role is onsite or hybrid |
| `L1_ARRANGEMENT_PARTIAL` | caution | Candidate wants hybrid and the role is onsite |
| `L1_ARRANGEMENT_DIFFERENT` | caution | Other mismatches (e.g. candidate wants onsite and the role is remote) |
| `L2_LOCATION_UNKNOWN` | unknown | Onsite or hybrid role with no location |
| `L2_COUNTRY_MISSING` | unknown | Candidate didn't give a country |
| `L2_COUNTRY_UNRECOGNISED` | unknown | Candidate's country text doesn't map to a known country. Comparisons are skipped, never treated as conflicts. |
| `L2_JOB_COUNTRY_UNKNOWN` | unknown | We can't map the location to one country |
| `L2_SAME_COUNTRY` | agreement | Office is in the candidate's country |
| `L2_RELOCATION_CONFLICT` | conflict | Office abroad and the candidate won't relocate |
| `L2_RELOCATION_NEEDED` | caution | Office abroad and the candidate is open to relocating. *Eligibility to work there stays unknown.* |
| `L3_REMOTE_COUNTRIES_UNSPECIFIED` | unknown | Remote role with no stated country or region limits |
| `L3_REMOTE_REGION_MATCH` | agreement | The stated region includes the candidate's country |
| `L3_REMOTE_REGION_CONFLICT` | conflict | The stated region excludes the candidate's country |
| `L3_REMOTE_REGION_UNCLEAR` | caution | A region is stated but we can't interpret it |
| `L3_REMOTE_REGION_COUNTRY_MISSING` | unknown | A region is stated but the candidate gave no country |
| `L3_LOCATION_REQUIREMENT` | caution | Non-remote role with a "must be located in X" that excludes the candidate |
| `L4_TIMEZONE` | caution | Working-hours or time-zone requirement stated |
| `L5_RELOCATION_REQUIRED_CONFLICT` | conflict | Listing requires relocation and the candidate won't relocate |
| `L5_RELOCATION_REQUIRED` | caution | Listing requires relocation |
| `L5_RELOCATION_ASSISTANCE` | agreement | Relocation assistance is mentioned |
| `L5_RELOCATION_NOT_OFFERED` | caution | Listing says there's no relocation support |

The section status is `conflict` if any finding conflicts. Otherwise it is `needs_clarification` if anything is unknown or a caution, `unknown` if the listing states neither an arrangement nor a location, and `compatible` in the remaining cases.

## Work authorization & sponsorship

The section label reflects **only the listing**:

| Listing states | Label |
|---|---|
| Both an offer and a restriction | `needs_clarification` (`A0_CONFLICTING_STATEMENTS`) |
| "Unable to sponsor" or "without sponsorship", or citizenship/clearance required | `explicitly_restricted` |
| "Happy to sponsor", "visa sponsorship available" | `explicitly_supported` |
| "Case by case" / "may sponsor" | `needs_clarification` |
| "Must be authorized to work in X" (without excluding sponsorship) | `needs_clarification` |
| Nothing | `not_specified` |

The candidate's answer then determines the finding status:

- `A1_PUBLISHED_RESTRICTION` is a **conflict** only when the candidate says they need sponsorship. It is a caution if they're unsure and an agreement if they don't need it.
- `A1_CITIZENSHIP_REQUIREMENT` is always at least a **caution** for citizenship or clearance requirements. Not needing sponsorship (e.g. holding a green card) doesn't satisfy "must be a U.S. citizen".
- `A5_NOT_SPECIFIED` is **unknown**, never treated as a no.
- `A6_REMOTE_INTERNATIONAL` is a caution on remote roles: whether remote work abroad needs a visa depends on the employment model, which listings rarely state.

Sponsorship is never inferred from salary, employer size, country, reputation or job title. The eval set includes cases for these traps.

## Technical alignment

This compares skills named in the listing, from a small curated vocabulary, with the candidate's skills after alias normalization (`k8s` → Kubernetes, and so on). The result is shown as supporting context only and is never combined with location or authorization.
