"""The evaluation set doubles as a regression gate for the deterministic extractor."""

from evals.run_evals import evaluate


async def test_eval_set_has_no_unsupported_claims_and_full_recall():
    res = await evaluate(use_llm=False)
    assert res["cases"] >= 15
    assert res["failures"] == [], res["failures"]
    assert res["unsupported_claim_rate"] == 0.0
