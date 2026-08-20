-- ===== 20260819120600_opportunities_action_rationale.sql =====
-- Aimfold Core — Recommended Action Rationale (PR9, schema addition)
--
-- aimfold_core/action/ (PR9) adds a deterministic Action Recommender
-- that picks opportunities.recommended_action (added in PR8) and also
-- produces a plain-language rationale for that pick — nowhere to store
-- it yet. Same small-additive-column pattern as PR6's
-- signals.evidence_model/evidence_prompt_version.

alter table public.opportunities
  add column if not exists recommended_action_rationale text;

comment on column public.opportunities.recommended_action_rationale is
  'Why aimfold_core.action.recommender.recommend_action() picked opportunities.recommended_action — includes the score/confidence thresholds and automation tier (discard_or_hold / deeper_research / surface_as_opportunity / prepare_action_automatically) that drove the decision.';
