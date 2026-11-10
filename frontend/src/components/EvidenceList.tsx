import { useId } from "react";
import { CircleHelp, Trash2 } from "lucide-react";
import { CATEGORY_LABEL, EXTRACTOR_LABEL, LLM_STATUS_TEXT, confidenceText, displayValue } from "../status";
import { CLAIM_CATEGORIES, type Claim, type ClaimCategory, type ExtractionReport } from "../types";

const SOURCE_LABEL: Record<Claim["evidence_source"], string> = {
  description: "description",
  "metadata.location": "listing metadata · location",
  "metadata.workplace_type": "listing metadata · workplace",
  "metadata.employment_type": "listing metadata · employment type",
  "metadata.remote": "listing metadata · remote flag",
};

function ExtractorBadge({ extractor }: { extractor: Claim["extractor"] }) {
  return (
    <span className="border-line text-ink-2 rounded border px-1 font-mono text-[10.5px] tracking-[0.04em] uppercase">
      {EXTRACTOR_LABEL[extractor]}
    </span>
  );
}

/** A single quoted piece of evidence with its source. */
export function EvidenceQuote({ claim }: { claim: Claim }) {
  return (
    <figure>
      <blockquote className="quote">“{claim.evidence_text}”</blockquote>
      <figcaption className="text-ink-3 mt-0.5 pl-3 font-mono text-[10.5px]">Source: {SOURCE_LABEL[claim.evidence_source]}</figcaption>
    </figure>
  );
}

function ClaimRow({ claim }: { claim: Claim }) {
  return (
    <li className="py-2.5 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-[13px] font-semibold">{displayValue(claim.value)}</span>
        <ExtractorBadge extractor={claim.extractor} />
        <span className="text-ink-2 cursor-help text-[11.5px] underline decoration-dotted underline-offset-2" title="Confidence is not proof">
          Confidence: {confidenceText(claim.confidence)}
        </span>
      </div>
      <div className="mt-1">
        <EvidenceQuote claim={claim} />
      </div>
    </li>
  );
}

interface EvidenceListProps {
  extraction: ExtractionReport;
}

export function EvidenceList({ extraction }: EvidenceListProps) {
  const grouped = new Map<ClaimCategory, Claim[]>();
  for (const c of extraction.claims) {
    const arr = grouped.get(c.category) ?? [];
    arr.push(c);
    grouped.set(c.category, arr);
  }
  const categories = CLAIM_CATEGORIES.filter((cat) => grouped.has(cat));
  const unknown = extraction.unknown_categories ?? [];
  const rejected = extraction.rejected_claims ?? [];
  const unknownId = useId();
  const rejectedId = useId();

  return (
    <div className="space-y-5">
      <p className="text-ink-2 font-mono text-[11.5px]">
        {LLM_STATUS_TEXT[extraction.llm_status ?? "disabled"]}
        {extraction.description_truncated ? " · long description truncated before analysis" : ""}
      </p>
      {extraction.injection_detected && (
        <p role="note" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900">
          This listing contains text addressed to AI tools. We ignored it: any AI-extracted claims were discarded,
          and only plainly stated, quoted requirements are shown.
        </p>
      )}

      {categories.length > 0 ? (
        <div className="space-y-4">
          {categories.map((cat) => (
            <section key={cat} aria-label={CATEGORY_LABEL[cat]}>
              <h4 className="eyebrow mb-2">{CATEGORY_LABEL[cat]}</h4>
              <ul className="divide-line divide-y">
                {grouped.get(cat)!.map((c) => (
                  <ClaimRow key={c.id} claim={c} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      ) : (
        <p className="text-ink-2 text-[13px]">No verifiable statements were found in this listing.</p>
      )}

      {unknown.length > 0 && (
        <section aria-labelledby={unknownId}>
          <h4 id={unknownId} className="eyebrow mb-2">
            Not stated in listing
          </h4>
          <ul className="flex flex-wrap gap-1.5">
            {unknown.map((cat) => (
              <li
                key={cat}
                className="border-neutral-line text-neutral inline-flex items-center gap-1 rounded-md border border-dashed px-1.5 py-px text-[12px]"
              >
                <CircleHelp aria-hidden="true" className="size-3" />
                {CATEGORY_LABEL[cat]}
              </li>
            ))}
          </ul>
          <p className="text-ink-3 mt-1.5 text-[12px]">Unknown means the listing is silent — not that the answer is no.</p>
        </section>
      )}

      {rejected.length > 0 && (
        <section aria-labelledby={rejectedId}>
          <h4 id={rejectedId} className="eyebrow mb-2">
            Discarded — quote not found in listing
          </h4>
          <ul className="space-y-2">
            {rejected.map((c) => (
              <li key={c.id} className="border-line rounded-lg border border-dashed p-2.5">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <Trash2 aria-hidden="true" className="text-ink-3 size-3.5" />
                  <span className="text-ink-2 text-[12.5px] font-medium line-through decoration-[#a8a29e]">
                    {CATEGORY_LABEL[c.category]}: {displayValue(c.value)}
                  </span>
                  <ExtractorBadge extractor={c.extractor} />
                </div>
                <p className="text-ink-3 mt-1 font-mono text-[12px] break-words">“{c.evidence_text}”</p>
                {c.rejection_reason && <p className="text-ink-2 mt-1 text-[12px]">Reason: {c.rejection_reason}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
