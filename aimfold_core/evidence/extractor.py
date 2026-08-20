"""Stage-1 evidence extraction: deterministic, no LLM.

This is the canonical Python implementation of the same rule-matching
logic that 06_leadgen_apify/collectiq_apify_multisource_leadgen_v03.json's
"Score Signal Against Aim" node runs in n8n — see
tests/test_evidence.py's test_matches_n8n_scorer_behavior for a
byte-for-byte cross-check. Having one canonical implementation matters
once a second Aim's connector isn't n8n-based; the n8n node stays for now
(06_leadgen_apify is unaffected by this PR) but new integrations should
call this instead of re-implementing the regex loop.
"""

from __future__ import annotations

import re

from aimfold_core.aim_compiler.schema import CompiledAimSpec

from .schema import EvidenceMatch, Stage1EvidenceResult


def extract_stage1_evidence(compiled_spec: CompiledAimSpec, normalized_text: str) -> Stage1EvidenceResult:
    text = (normalized_text or "").lower()
    matches: list[EvidenceMatch] = []
    score = 0
    for rule in compiled_spec.scoring_weights:
        m = re.search(rule.pattern, text)
        if m:
            matches.append(EvidenceMatch(pattern=rule.pattern, label=rule.label, points=rule.points, matched_text=m.group(0)))
            score += rule.points

    max_score = compiled_spec.confidence_thresholds.max_score
    score = min(score, max_score)
    qualifies = score >= compiled_spec.confidence_thresholds.qualified_signal_min_score

    return Stage1EvidenceResult(matches=matches, score=score, max_score=max_score, qualifies=qualifies)
