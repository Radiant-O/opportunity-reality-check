import { ChevronRight } from "lucide-react";
import { FINDING_STATUS } from "../status";
import type { Claim, Finding } from "../types";
import { TONE_TEXT } from "./StatusBadge";
import { EvidenceQuote } from "./EvidenceList";

interface FindingListProps {
  findings: Finding[];
  claimsById: ReadonlyMap<string, Claim>;
}

export function FindingList({ findings, claimsById }: FindingListProps) {
  if (findings.length === 0) {
    return <p className="text-ink-2 text-[13px]">No specific findings for this section.</p>;
  }
  return (
    <ul className="divide-line divide-y">
      {findings.map((f) => {
        const meta = FINDING_STATUS[f.status];
        const Icon = meta.icon;
        const claims = (f.evidence_claim_ids ?? [])
          .map((id) => claimsById.get(id))
          .filter((c): c is Claim => Boolean(c));
        return (
          <li key={f.rule_id} className="flex gap-2.5 py-2.5 first:pt-0 last:pb-0">
            <Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${TONE_TEXT[meta.tone]}`} strokeWidth={2.25} />
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] leading-snug font-semibold">
                <span className="sr-only">{meta.label}: </span>
                {f.title}
              </p>
              <p className="text-ink-2 mt-0.5 text-[13px] leading-relaxed">{f.explanation}</p>
              <p className={`mt-1 text-[11.5px] font-medium ${TONE_TEXT[meta.tone]}`} aria-hidden="true">
                {meta.label}
              </p>
              {claims.length > 0 ? (
                <details className="group mt-1.5">
                  <summary className="text-accent hover:text-accent-hover inline-flex items-center gap-0.5 rounded text-[12.5px] font-medium">
                    <ChevronRight aria-hidden="true" className="size-3.5 transition-transform duration-150 group-open:rotate-90" />
                    Evidence ({claims.length})
                  </summary>
                  <div className="mt-1.5 space-y-1.5">
                    {claims.map((c) => (
                      <EvidenceQuote key={c.id} claim={c} />
                    ))}
                  </div>
                </details>
              ) : (
                <p className="text-ink-3 mt-1 text-[12px]">No quote — the listing doesn’t state this.</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
