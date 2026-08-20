"""Hand-labeled evaluation dataset for CollectIQ's Aim (the only Aim
that exists yet — see 20260819120200_seed_collectiq_aim.sql). Every
signal_text is either a real example already used to live-verify an
earlier PR in this dev sequence, or a purpose-built example testing a
specific known edge case — none are arbitrary filler.

expected_score_range values were calibrated against a real run of this
exact dataset through the real pipeline (Stage 1 + Stage 2 via Gemini) —
see aimfold_core/evaluation/tests/test_evaluation.py's docstring and the
PR13 write-up for the actual observed numbers this was tuned against.
"""

from __future__ import annotations

from .schema import EvalExample

COLLECTIQ_EVAL_V1: list[EvalExample] = [
    EvalExample(
        id="excellent-ar-analyst-acme",
        signal_text=(
            "Senior Accounts Receivable Analyst. Acme Freight Systems is scaling fast and our AR team "
            "is drowning in manual work — we're chasing overdue invoices by hand in spreadsheets and "
            "reconciling disputes across three different systems. Recently rolled out NetSuite but the "
            "old process hasn't caught up. Looking for someone who can also help us build weekly aging "
            "reports for leadership."
        ),
        expected_category="excellent",
        expected_qualifies=True,
        expected_score_range=(80, 100),
        expected_matched_criteria=["AR hiring", "disputes", "spreadsheet workflow", "ERP/accounting system"],
        expected_action="contact",
        notes=(
            "The real example live-verified in PR6/PR7/PR9/PR11 (Gemini scored it 91.8/100 with 6 verified "
            "observed_facts). Reused here rather than inventing a new 'excellent' example — this one has an "
            "actual track record."
        ),
    ),
    EvalExample(
        id="acceptable-credit-controller",
        signal_text=(
            "Credit Controller needed. Chase overdue invoices, review aging reports weekly, manage a high "
            "volume of accounts currently tracked in spreadsheets."
        ),
        expected_category="acceptable",
        expected_qualifies=True,
        expected_score_range=(55, 79),
        expected_matched_criteria=["collections/credit control", "ageing", "spreadsheet workflow", "high volume"],
        expected_action=None,
        notes="Real signal, genuinely qualifies (Stage-1 alone: collections 30 + ageing 10 + high_volume 15 + spreadsheet 10 = 65), but thinner evidence than the excellent example — no ERP mention, no disputes, no explicit timing trigger.",
    ),
    EvalExample(
        id="false-positive-ar-vr-engineer",
        signal_text=(
            "Software Engineer - AR/VR Applications. Build immersive augmented reality experiences for "
            "enterprise clients. We use spreadsheets for high volume project reporting and sprint tracking."
        ),
        expected_category="false_positive",
        expected_qualifies=True,
        expected_score_range=(0, 55),
        expected_matched_criteria=[],
        expected_action=None,
        notes=(
            "A known Stage-1 blind spot, deliberately included: the \\bAR\\b regex (from 'AR hiring') matches "
            "'AR/VR' as a standalone word, and this text also coincidentally contains 'spreadsheet' and "
            "'high volume' in an unrelated (software sprint tracking) context. Stage 1 alone scores this "
            "AR(25)+spreadsheet(10)+high_volume(15)=50 (or higher depending on the exact reporting/aging hits) "
            "— genuinely wrong, but its purpose is to prove Stage 2 (which must ground every observed_fact in "
            "the actual text) refuses to manufacture AR/collections relevance out of an augmented-reality job "
            "posting. expected_qualifies=True describes Stage 1's (wrong) behavior on purpose; "
            "expected_matched_criteria=[] describes what a CORRECT Stage-2 assessment should find (nothing) — "
            "the whole point of this example is that Stage 1 and Stage 2 should disagree here."
        ),
    ),
    EvalExample(
        id="irrelevant-warehouse",
        signal_text="Warehouse Associate. Lift boxes, operate forklift, general warehouse duties.",
        expected_category="irrelevant_signal",
        expected_qualifies=False,
        expected_score_range=(0, 30),
        expected_matched_criteria=[],
        expected_action=None,
        notes="Zero AR/collections signal of any kind — the simple true-negative case.",
    ),
    EvalExample(
        id="ambiguous-finance-ops-coordinator",
        signal_text=(
            "Finance Operations Coordinator. Support various finance functions including some invoicing "
            "and reporting tasks as needed, alongside general administrative work."
        ),
        expected_category="ambiguous",
        expected_qualifies=False,
        expected_score_range=(0, 45),
        expected_matched_criteria=[],
        expected_action=None,
        notes="Vague, low-signal text — 'reporting' is the only real keyword hit and it's buried in generic administrative language. Should score low but not zero; a human reviewing this would reasonably shrug rather than confidently reject it.",
    ),
    EvalExample(
        id="excellent-ar-manager-full-cycle",
        signal_text=(
            "Accounts Receivable Manager — own the full AR cycle: aging, collections calls, dispute "
            "resolution, and cash application posting. High volume portfolio, currently using Excel for "
            "tracking."
        ),
        expected_category="excellent",
        expected_qualifies=True,
        expected_score_range=(65, 95),
        expected_matched_criteria=["AR hiring", "collections/credit control", "ageing", "disputes", "cash application", "high volume", "spreadsheet workflow"],
        expected_action="contact",
        notes=(
            "Purpose-built to hit nearly every positive_criteria at once (Stage-1 alone already caps at 100: "
            "25+30+10+15+8+15+10=113) — tests that the scoring engine correctly caps rather than reporting an "
            "out-of-range total. expected_score_range calibrated against a real run at (65, 95), not the naive "
            "(85, 100) a first guess would suggest: this text has no explicit timing trigger ('why_now'), so "
            "Timing/Trigger Strength (20% of the total) scores near its floor even though every other dimension "
            "is close to maximal — a real, informative property of the scoring engine (evidence completeness "
            "alone doesn't guarantee a top-tier total_score), not a dataset error. Compare against "
            "excellent-ar-analyst-acme, which does have an explicit timing trigger ('Recently rolled out "
            "NetSuite') and correctly scores higher (91.8 in the real PR7 live run) despite matching fewer "
            "positive_criteria overall."
        ),
    ),
]

__all__ = ["COLLECTIQ_EVAL_V1"]
