"""Second labeled evaluation dataset — AIMFOLD_MASTER_GOAL.md section 41
(Horizontal Validation): proves aimfold_core/evaluation itself
generalizes to a materially different Aim, not just the pipeline it
tests. Evaluated against the Career Discovery Aim seeded by
20260819121100_seed_career_discovery_aim.sql (compiled_spec produced
live by the real, unmodified Aim Compiler — see that migration's header).

Same five evaluable categories as dataset.py's COLLECTIQ_EVAL_V1, same
scoping rationale (see evaluation/schema.py's module docstring for why
stale/revived/multi-signal aren't dataset categories).
"""

from __future__ import annotations

from .schema import EvalExample

CAREER_DISCOVERY_EVAL_V1: list[EvalExample] = [
    EvalExample(
        id="excellent-vp-finance-transformation",
        signal_text=(
            "VP of Finance Transformation & Systems. Own our multi-year finance transformation "
            "roadmap: financial systems modernization, process reengineering, and building out our "
            "finance data analytics capability from the ground up."
        ),
        expected_category="excellent",
        expected_qualifies=True,
        expected_score_range=(75, 100),
        expected_matched_criteria=[
            "role involves finance transformation, process reengineering, or financial systems implementation",
            "role sits at the intersection of finance and data analytics or engineering",
        ],
        expected_action=None,
        notes=(
            "Hits all three of the Career Aim's scoring_weights rules at once (finance transformation + "
            "financial systems/process reengineering + finance data analytics) — Stage-1 alone caps at 100 "
            "(40+30+30=100). expected_action is deliberately None, not 'apply': the live run scored this "
            "76.1/0.65 confidence — inside prepare_action_automatically's score bar (>=80... narrowly missed) "
            "but confidence never clears 0.7 here, because this evaluation harness never sets a real "
            "signals.source_quality (score_signal defaults it to a neutral 0.5), which structurally caps "
            "confidence at (evidence_confidence+0.5)/2 regardless of how good the evidence is. A real pipeline "
            "with actual source-quality tracking would score this differently — that's a harness gap, not "
            "something to paper over by asserting an action this dataset can't reliably produce."
        ),
    ),
    EvalExample(
        id="acceptable-senior-financial-analyst",
        signal_text=(
            "Senior Financial Analyst - Data & Analytics. Join our finance data analytics team, "
            "working on process reengineering and business intelligence dashboards for FP&A."
        ),
        expected_category="acceptable",
        expected_qualifies=True,
        expected_score_range=(45, 78),
        expected_matched_criteria=["role sits at the intersection of finance and data analytics or engineering"],
        expected_action=None,
        notes=(
            "Qualifies (Stage-1: financial systems/process reengineering 30 + finance data/analytics/BI 30 = "
            "60) but doesn't name 'finance transformation' explicitly the way the excellent example does — "
            "real, thinner evidence, not a top-tier match. Range's upper bound calibrated to 78 (not a tighter "
            "guess like 74) after a live run scored this 74.85 — Gemini judged the evidence here more "
            "favorably than the Stage-1 gap to the excellent example alone would suggest, matching all three "
            "positive_criteria rather than the single one this dataset requires (a superset is fine, "
            "grounding is a recall check)."
        ),
    ),
    EvalExample(
        id="false-positive-marketing-analytics",
        signal_text=(
            "Marketing Analytics Manager. We're looking for someone with strong analytics and "
            "business intelligence skills to support our marketing process reengineering "
            "initiatives, using data warehousing to modernize our systems."
        ),
        expected_category="false_positive",
        expected_qualifies=True,
        expected_score_range=(0, 44),
        expected_matched_criteria=[],
        expected_action=None,
        notes=(
            "A known Stage-1 blind spot, deliberately included (same purpose as PR13's AR/VR example): "
            "this is a MARKETING analytics role that coincidentally uses finance-transformation-adjacent "
            "buzzwords ('process reengineering', 'business intelligence', 'modernize... systems'). Stage 1 "
            "alone scores it financial systems/process reengineering (30) + finance data/analytics/BI (30) "
            "= 60, wrongly qualifying — there is no actual finance function involved.\n\n"
            "UNLIKE PR13's AR/VR example, a live run did NOT cleanly catch this one: Stage 2 scored it "
            "58.6/100 and matched 2 of 3 positive_criteria (the ideal, expected result stays 0/[] — left "
            "as-is on purpose rather than loosened to match what happened). Gemini's own relevance_explanation "
            "even noted \"it is situated in a marketing context rather than a finance department\" but still "
            "credited partial criteria matches for the literal 'process reengineering'/'modernize... systems' "
            "phrases. This is a genuine, disclosed limitation, not a bug to quietly paper over: this Aim's "
            "positive_criteria (Aim-Compiler-generated, unedited — see the seed migration) are worded more "
            "abstractly than CollectIQ's crisp AR-specific ones ('job description emphasizes modernizing or "
            "scaling finance operations' doesn't require the word finance to appear near 'modernizing'), which "
            "gives Stage 2 more room to credit a topically-adjacent-but-wrong-domain posting. A future "
            "iteration on this Aim's wording (via a learning_proposal, PR15) is the right fix — not hand-"
            "editing the Compiler's output after the fact, which would defeat the point of horizontal "
            "validation (AIMFOLD_MASTER_GOAL.md section 41)."
        ),
    ),
    EvalExample(
        id="irrelevant-warehouse-operations",
        signal_text="Warehouse Operations Associate. Manage inventory, operate forklift, coordinate shipping schedules.",
        expected_category="irrelevant_signal",
        expected_qualifies=False,
        expected_score_range=(0, 20),
        expected_matched_criteria=[],
        expected_action=None,
        notes="Zero finance/data signal of any kind — the simple true-negative case.",
    ),
    EvalExample(
        id="ambiguous-finance-business-partner",
        signal_text="Finance Business Partner. Support various analytics initiatives across the finance function as needed.",
        expected_category="ambiguous",
        expected_qualifies=False,
        expected_score_range=(0, 39),
        expected_matched_criteria=[],
        expected_action=None,
        notes="Vague, low-signal text — 'analytics' is the only real keyword hit (30, below the 40 threshold) and it's buried in generic language. Borderline, not clearly good or bad.",
    ),
]

__all__ = ["CAREER_DISCOVERY_EVAL_V1"]
