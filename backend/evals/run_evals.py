"""Run the extraction evaluation set and print per-category precision/recall.

Usage:  python -m evals.run_evals            (deterministic extractor)
        python -m evals.run_evals --llm      (also run the LLM extractor; needs ANTHROPIC_API_KEY)

Scoring is set-based per (case, category): an extracted value counts as a true
positive if it is in the expected set ("Time zone:*" matches any time-zone
value). Every expected category list is exhaustive, so anything extra is a
false positive ("unsupported claim").
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from app.config import get_settings
from app.extraction.llm import LLMExtractor
from app.extraction.pipeline import run_extraction
from app.models import JobDetail

CASES = Path(__file__).with_name("cases.json")


def load_cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def _match(value: str, expected: set[str]) -> bool:
    return value in expected or (value.startswith("Time zone") and "Time zone:*" in expected)


async def evaluate(use_llm: bool = False) -> dict:
    llm = LLMExtractor(get_settings()) if use_llm else None
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    failures: list[str] = []
    total_claims = rejected_claims = 0
    for case in load_cases():
        j = case["job"]
        job = JobDetail(
            id=case["id"], title="Eval role", company="Eval Co", url="https://speedrun-talent-network.com/jobs/x",
            location=j.get("location"), workplace_type_raw=j.get("workplace_type"),
            description_text=j.get("description_text"),
        )
        report = await run_extraction(job, llm)
        total_claims += len(report.claims)
        rejected_claims += len(report.rejected_claims)
        for cat, expected_list in case["expected"].items():
            expected = set(expected_list)
            got = {c.value for c in report.claims if c.category.value == cat}
            matched_expected = set()
            for v in got:
                if _match(v, expected):
                    stats[cat]["tp"] += 1
                    matched_expected.add("Time zone:*" if v.startswith("Time zone") else v)
                else:
                    stats[cat]["fp"] += 1
                    failures.append(f"{case['id']}: unexpected {cat}={v}")
            for e in expected - matched_expected:
                stats[cat]["fn"] += 1
                failures.append(f"{case['id']}: missed {cat}={e}")
    summary = {}
    for cat, s in sorted(stats.items()):
        p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else 1.0
        r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else 1.0
        summary[cat] = {**s, "precision": round(p, 3), "recall": round(r, 3)}
    fp_total = sum(s["fp"] for s in stats.values())
    tp_total = sum(s["tp"] for s in stats.values())
    return {
        "cases": len(load_cases()),
        "per_category": summary,
        "unsupported_claim_rate": round(fp_total / (fp_total + tp_total), 3) if fp_total + tp_total else 0.0,
        "verified_claims": total_claims,
        "rejected_claims": rejected_claims,
        "failures": failures,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    res = asyncio.run(evaluate(args.llm))
    print(f"Cases: {res['cases']}")
    print(f"{'category':26} {'tp':>4} {'fp':>4} {'fn':>4} {'precision':>10} {'recall':>8}")
    for cat, s in res["per_category"].items():
        print(f"{cat:26} {s['tp']:>4} {s['fp']:>4} {s['fn']:>4} {s['precision']:>10.3f} {s['recall']:>8.3f}")
    print(f"Unsupported-claim rate (scored categories): {res['unsupported_claim_rate']:.3f}")
    print(f"Rejected by evidence validation: {res['rejected_claims']}")
    if res["failures"]:
        print("\nMisses / extras:")
        for f in res["failures"]:
            print(" -", f)


if __name__ == "__main__":
    main()
