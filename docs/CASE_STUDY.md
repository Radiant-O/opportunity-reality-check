# Case study: Opportunity Reality Check

## The problem

A job listing answers "what is the job?" well and "is this job realistic for *me*?" badly. For candidates outside the role's country, the deciding facts are sponsorship, onsite requirements, which countries "remote" covers, and relocation. These are often missing, buried in benefits sections, or contradicted between the board's labels and the text.

I sampled 39 live engineering listings from the speedrun API while building this. Only a handful said anything explicit about visa sponsorship (three stated an offer). Several described onsite expectations in more detail than the board's workplace label, for example "in person 4–5 days per week". Both remote listings in the sample restricted applicants by time zone or working hours rather than by country. Most of what a non-US candidate needs to know is simply **not stated**, and that is the case the product must handle best.

## The product bet

Don't predict eligibility. **Make the listing's own statements legible, and make silence visible.**

That means three things the UI keeps separate:

1. **What the listing states** (quoted, linkable to the source field)
2. **What it doesn't** ("Not specified" is unknown, not a no)
3. **What that means for you** (rule-based findings relative to your stated preferences)

The output ends in action: a ranked checklist and a draft question to send, since the real resolution almost always comes from asking the employer.

## Key decisions and trade-offs

| Decision | Why | Cost |
|---|---|---|
| Deterministic extractor first, LLM optional | Precise, explainable, free, testable. Real listings use fairly regular phrasing for the facts that matter. | Lower recall on unusual phrasing (falls back to "Not specified") |
| Every claim must quote its source; validator rejects otherwise | Makes fabrication structurally impossible to reach the user, and makes injection testable | Some legitimate paraphrased LLM claims get discarded |
| Polarity cross-check on LLM claims | Catches the worst failure (the model says "offered" when the quote says "unable to sponsor") | Depends on the deterministic classifier's coverage |
| Rules engine with ids, no overall score | A single percentage hides why; candidates need the specific blocker | Less "at a glance" |
| Description beats label for work arrangement, with a flag | Text is more specific; disagreement is itself useful info | Rare cases where the label is right and the text is stale |
| No accounts, no storage | Immigration status and nationality are sensitive; nothing here needs persistence | No saved searches |
| Clarity Check uses deterministic extraction only | Anonymous pasted text shouldn't drive LLM spend | Fewer nuances detected for founders |

## What I deliberately did not build

- An ATS, an application auto-submitter, or a resume writer
- A chat interface. This is a structured decision aid.
- Any legal determination. The authorization section reports only what the posting establishes.

## Validation plan (not yet run)

I haven't run user tests. No user numbers are claimed here. The plan:

**Participants:** 5–8 international job seekers (mixed sponsorship needs) and 3–5 founders or hiring managers.

**Tasks (candidate):** for two live listings, first using only the speedrun page and then with the tool (order counterbalanced):

1. "Does this role sponsor visas?"
2. "Can you do this job from where you live?"
3. "What would you ask the employer before applying?"

**Measures:**

- Time to identify critical constraints
- Accuracy of answers against a ground-truth reading of the listing
- Whether participants distinguish "Not specified" from "Explicitly restricted", probed with a listing of each kind
- Whether the next steps match what they'd do
- Self-reported effort

**Founder task:** run Listing Clarity Check on one of their own listings. Ask whether the gaps are accurate, and whether they would edit the listing.

**Extraction quality:** have someone other than the rules' author label 50 random live listings, then report per-category precision and recall and the unsupported-claim rate for the deterministic and LLM paths separately. The current 16-case eval set is a regression gate, not an accuracy estimate.

## What I'd do next

1. Run the labelled-listing study above and use misses to extend patterns or to justify enabling the LLM path in production.
2. Offer founders a "suggested sentence" they can paste straight into their posting (e.g. "We can sponsor H-1B and O-1 visas for this role").
3. Aggregate, anonymised clarity stats across the board ("x% of listings don't mention sponsorship"). This could be useful feedback for the speedrun team, if they wanted it.
