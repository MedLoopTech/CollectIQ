"""Third labeled evaluation dataset — AIMFOLD_MASTER_GOAL.md section 41
(Horizontal Validation): proves aimfold_core/evaluation generalizes to a
third, materially different Aim. Evaluated against the Funding Discovery
Aim seeded by 20260819121300_seed_funding_discovery_aim.sql (compiled_spec
produced live by the real, unmodified Aim Compiler — see that migration's
header).

Same five evaluable categories as dataset.py's COLLECTIQ_EVAL_V1 and
dataset_career_discovery.py's CAREER_DISCOVERY_EVAL_V1, same scoping
rationale (see evaluation/schema.py's module docstring).
"""

from __future__ import annotations

from .schema import EvalExample

FUNDING_DISCOVERY_EVAL_V1: list[EvalExample] = [
    EvalExample(
        id="excellent-adb-climate-health-facility",
        entity_type="grant",
        signal_text=(
            "The Asian Development Bank has issued a call for proposals for its Climate Resilient "
            "Health Infrastructure Grant Facility, providing funding to public health authorities in "
            "Southeast Asia and Sub-Saharan Africa to build climate-adaptive hospitals and clinics "
            "resilient to extreme weather and flooding."
        ),
        expected_category="excellent",
        expected_qualifies=True,
        expected_score_range=(75, 100),
        expected_matched_criteria=[
            "opportunity is an active grant or funding program",
            "focuses on climate change impacts on health or health infrastructure",
            "targets emerging markets or developing economies",
        ],
        expected_action=None,
        notes=(
            "Hits all three of the Funding Aim's scoring_weights rules at once (call for proposals + "
            "climate/resilience + health/hospital/clinic) — Stage-1 alone caps at 100 (40+30+30=100), "
            "clearing the 70 qualified_signal_min_score by a wide margin. expected_action left None "
            "pending a live run, same rationale as the Career Discovery dataset's excellent example: this "
            "harness never sets a real signals.source_quality, so confidence is structurally capped and "
            "prepare_action_automatically's >=0.7 confidence gate is not reliably reproducible here."
        ),
    ),
    EvalExample(
        id="acceptable-foundation-hospital-grant-no-climate-framing",
        entity_type="grant",
        signal_text=(
            "A major foundation announced a new grant program supporting hospital construction and "
            "public health system strengthening across several low- and middle-income countries in "
            "South Asia and East Africa."
        ),
        expected_category="acceptable",
        expected_qualifies=True,
        expected_score_range=(45, 95),
        expected_matched_criteria=[
            "opportunity is an active grant or funding program",
            "focuses on climate change impacts on health or health infrastructure",
        ],
        expected_action=None,
        notes=(
            "Qualifies on Grant Mechanism (grant program, 40) + Health Infrastructure Focus (hospital, "
            "public health, 30) = 70, exactly at the threshold — never names climate/resilience "
            "explicitly, only geography ('South Asia and East Africa') implying emerging markets. Two "
            "live runs scored this 70.1/0.6 and 84.1/0.6 respectively (real Stage-2 evidence_confidence "
            "non-determinism between calls, not a bug) and both matched all three positive_criteria, not "
            "just the two this dataset requires — Gemini correctly read the named regions as evidence of "
            "'targets emerging markets or developing economies' even without the word 'emerging' "
            "appearing. A superset match is fine here (grounding is a recall check, same convention as "
            "the Career Discovery dataset's acceptable example); expected_matched_criteria stays the "
            "narrower two-criteria list since that's the minimum a correct assessment must find, not the "
            "maximum. Range widened to (45,95), not tightened to either single observed run, to absorb "
            "this real run-to-run variance rather than risk test flakiness."
        ),
    ),
    EvalExample(
        id="false-positive-domestic-hospital-equipment-grant",
        entity_type="grant",
        signal_text=(
            "The state health department has opened a competitive grant program to fund hospital "
            "equipment modernization at public health clinics, with awards available to eligible "
            "healthcare facilities statewide."
        ),
        expected_category="false_positive",
        expected_qualifies=True,
        expected_score_range=(30, 50),
        expected_matched_criteria=["opportunity is an active grant or funding program"],
        expected_action=None,
        notes=(
            "A known Stage-1 blind spot, deliberately included (same purpose as PR13's AR/VR example and "
            "PR16's marketing-analytics example): this is a purely DOMESTIC (implicitly US, 'statewide') "
            "hospital equipment grant with zero climate angle and zero emerging-markets angle. Stage 1 "
            "alone scores it Grant Mechanism (grant program, 40) + Health Infrastructure Focus (health "
            "clinics/healthcare facilities, 30) = 70, wrongly qualifying on keyword overlap alone.\n\n"
            "UNLIKE PR16's marketing-analytics example, a live run shows Stage 2 correctly RECOVERING "
            "from Stage 1's blind spot here: it scored this 45.1/100 (well below the 70 acceptable "
            "threshold) and matched only the one positive_criterion that is actually true ('opportunity "
            "is an active grant or funding program' — it genuinely is one), correctly declining to credit "
            "the climate-health-intersection or emerging-markets criteria this text has no evidence for. "
            "A genuine, disclosed finding, just a different one than expected going in: this Aim's "
            "positive_criteria are worded narrowly enough (each criterion maps to a distinct, checkable "
            "fact) that Stage 2 handles this false positive well, in contrast to the Career Discovery "
            "Aim's more abstractly-worded criteria which let a comparable false positive through "
            "(20260819121100's marketing-analytics example). The interesting result this example "
            "actually demonstrates is the two-stage design working as intended, not a limitation."
        ),
    ),
    EvalExample(
        id="irrelevant-school-sports-equipment-grant",
        entity_type="grant",
        signal_text=(
            "The local school district announced a small grant available to elementary schools for "
            "new playground and sports equipment purchases."
        ),
        expected_category="irrelevant_signal",
        expected_qualifies=False,
        expected_score_range=(0, 50),
        expected_matched_criteria=[],
        expected_action=None,
        notes=(
            "Only ever hits the single Grant Mechanism keyword (grant, 40 points) — structurally cannot "
            "reach the 70-point qualified_signal_min_score on Grant Mechanism alone, since Climate Focus "
            "and Health Infrastructure Focus require entirely different vocabulary this text has none of. "
            "Stage 1 correctly disqualifies it (stage1_qualifies=False, as predicted) and Stage 2 never "
            "runs. Range widened from an initial (0,44) guess to (0,50) after a live run scored this "
            "45.0 — total_score isn't a linear pass-through of stage1_score even when Stage 2 doesn't "
            "run (score_signal blends in a neutral baseline confidence), so a disqualified signal's "
            "total_score can land a little above its own stage1_score. The simple true-negative case: "
            "zero climate/health signal of any kind, correctly never reaching Stage 2."
        ),
    ),
    EvalExample(
        id="ambiguous-generic-funding-mechanism",
        entity_type="grant",
        signal_text=(
            "An organization is exploring new funding mechanisms to support various global development "
            "initiatives across several countries."
        ),
        expected_category="ambiguous",
        expected_qualifies=False,
        expected_score_range=(0, 39),
        expected_matched_criteria=[],
        expected_action=None,
        notes=(
            "Vague, low-signal text — 'funding mechanisms' does not literally match the Grant Mechanism "
            "pattern ('grant|funding opportunity|call for proposals|request for applications'), and there "
            "is no climate or health vocabulary at all. Reads superficially adjacent to the Aim's domain "
            "('global development', 'various countries') without containing any of its actual scoring "
            "keywords — borderline, not clearly good or bad, structurally similar to the Career Discovery "
            "dataset's ambiguous example."
        ),
    ),
]

__all__ = ["FUNDING_DISCOVERY_EVAL_V1"]
