# aimfold_core

Generic Aimfold engine code — as opposed to the `0X_*` directories, which
are the CollectIQ pilot (soon to be "just" the first Aim, per
`AIMFOLD_MASTER_GOAL.md` section 40: *"CollectIQ should become a
validation Aim, not remain embedded in the core engine."*). Nothing in
here should ever import from or hardcode assumptions from `01_landing_intake`
through `06_leadgen_apify`.

## What's here

### `aim_compiler/` (PR4)

Turns a user's natural-language intent into a validated, structured Aim.

- `schema.py` — `CompiledAimSpec`, the pydantic contract for
  `aim_versions.compiled_spec` (formalizes what
  `supabase/migrations/20260819120100_aim_schema.sql` left as an
  unvalidated jsonb blob). Field names match
  `AIMFOLD_MASTER_GOAL.md` section 4 exactly.
- `prompt.py` — the compiler's system/user prompt templates, versioned via
  `PROMPT_VERSION`.
- `llm_client.py` — a model-independent `LLMClient` interface
  (`AIMFOLD_MASTER_GOAL.md` section 27), real `AnthropicLLMClient` and
  `GeminiLLMClient` adapters, `build_llm_client_from_env()` (picks
  between them via `AI_PROVIDER=anthropic|gemini`, same convention as the
  sibling `sehat90` project), and a `StubLLMClient` used only by tests.
  `GeminiLLMClient` defaults to the `gemini-flash-latest` alias rather
  than a pinned version — sehat90's own notes flagged `gemini-1.5-flash`
  and `gemini-2.5-flash` as retired on that key.
- `compiler.py` — `compile_aim(raw_user_intent, llm_client)`: calls the
  model, parses its JSON, validates against `CompiledAimSpec`, retries up
  to 3 times on validation failure with the error fed back to the model,
  and raises `AimCompilationError` if it still can't produce something
  valid.
- `api.py` — thin FastAPI wrapper. `POST /aims/compile` (same shape as
  `02_audit_engine/api.py`) proposes; `POST /aims/propose` persists —
  re-validates the exact `compiled_spec` the caller already has via the
  same `CompiledAimSpec` model, verifies the caller's identity and real
  tenant membership, then writes `aims`/`aim_versions` with a
  service-role key the caller never sees. See
  `aimfold_core/portal/README.md`'s "New Aim" section for the full
  design rationale and live verification (including three attack tests
  — foreign tenant, missing auth, malformed spec — all correctly
  rejected) — built there, alongside the portal's Create-Aim UI that
  calls it.
- `tests/test_compiler.py` — run with
  `python aimfold_core/aim_compiler/tests/test_compiler.py` (no pytest
  dependency, same convention as `02_audit_engine/test_golden.py`).
  Notably, one test loads the *real* CollectIQ `compiled_spec` straight
  out of `supabase/migrations/20260819120200_seed_collectiq_aim.sql` and
  validates it against `CompiledAimSpec` — if PR3's seed data and PR4's
  schema ever drift apart, that test fails.

A live `GEMINI_API_KEY` is configured (gitignored, `aimfold_core/aim_compiler/.env`,
`AI_PROVIDER=gemini`) and `compile_aim()` has been run against it successfully
end-to-end — not just the stub. `gemini-flash-latest` (the default model) is
occasionally 503 ("high demand") under real traffic; `gemini-flash-lite-latest`
is a working fallback if that happens, pass `GeminiLLMClient(model=...)`
directly to override.

### What PR4 does **not** do yet

1. ~~No persistence.~~ Closed — `POST /aims/propose` (above) is that
   flow: real service-role writes to `aims`/`aim_versions`, gated by a
   real re-validation + identity + tenant-membership check, wired up end
   to end from the portal's "New Aim" UI. Left here so the history of
   this gap being identified and later closed stays visible.
2. **Not yet used by the n8n workflow.** `06_leadgen_apify`'s v0.3
   workflow reads an already-approved, already-current `aim_versions` row
   — it has no dependency on this compiler. This module is for *creating
   new* Aims (or new versions of existing ones) going forward, starting
   with the second/third validation Aims required by
   `AIMFOLD_MASTER_GOAL.md` section 41.

### `evidence/` (PR6)

Two-stage evidence extraction for a Signal, per `AIMFOLD_MASTER_GOAL.md`
section 8 (Evidence-First) and section 14 (Two-Stage Evaluation).

- `schema.py` — `EvidenceMatch`/`Stage1EvidenceResult` (deterministic),
  `EvidenceAssessment` (LLM), `EvidenceEvaluationResult` (combined).
- `extractor.py` — `extract_stage1_evidence()`: the same regex-scoring
  logic as `06_leadgen_apify`'s "Score Signal Against Aim" n8n node,
  reimplemented once in Python as the canonical version (verified
  byte-for-byte identical output in `tests/test_evidence.py` — the n8n
  node itself is untouched by this PR). No LLM call, runs for every signal.
- `evaluator.py` — `evaluate_evidence()`: the Stage-2 LLM call, only
  reached for signals that already qualify at Stage 1. Enforces
  Evidence-First **in code, not just in the prompt**: every
  `observed_fact` the model returns is checked to be a literal substring
  of the signal's own text, and every `matched_positive_criteria` entry
  is checked against the Aim's real `positive_criteria` list — either
  check failing triggers the same retry-with-feedback loop as
  `aim_compiler.compiler`, and raises `EvidenceEvaluationError` if the
  model still can't produce something non-fabricated after 3 attempts.
- `pipeline.py` — `assess_signal_evidence()`: runs Stage 1 always; runs
  Stage 2 only if Stage 1 qualifies *and* an `llm_client` was passed
  (pass `None` to force Stage-1-only).
- `tests/test_evidence.py` — 9 tests, all passing, including two that
  feed a fabricated observed_fact / an invented criterion through
  `_SequenceLLMClient` and assert they're rejected. Also live-verified
  against real Gemini (not just the stub): given a synthetic job posting,
  it correctly quoted six real substrings as `observed_facts`, kept three
  interpretive claims separately in `inferences`, and set
  `evidence_strength: 0.95` — the fabrication check passed on genuine
  model output, not just on hand-crafted bad-input test fixtures.

Not done in PR6: nothing writes results back onto a `signals` row yet
(no service-role wiring exists here, same limitation as PR4's compiler),
and `06_leadgen_apify`'s workflow doesn't call any of this — it still
does its own Stage-1 scoring inline in n8n. `signals.evidence_model` /
`evidence_prompt_version` (added in
`20260819120400_signals_evidence_versioning.sql`) are ready for when
persistence is wired up.

### `scoring/` (PR7)

The explainable scoring engine — `AIMFOLD_MASTER_GOAL.md` section 13's
seven weighted dimensions (Aim Fit 20 / Evidence Strength 25 /
Timing-Trigger Strength 20 / Opportunity Relevance 15 / Evidence
Confidence 10 / Source Quality 5 / Actionability 5, summing to 100).

- `schema.py` — `ScoringWeights` (validates weights sum to 100, `extra:
  forbid`), `DimensionScore` (weight + raw 0-1 value + weighted points +
  plain-language rationale — never just a number), `ExplainableScore`
  (all seven `DimensionScore`s + `total_score` + `scoring_version` +
  `weights_used`, so a stored score is fully reconstructable later).
- `engine.py` — `score_signal(compiled_spec, stage1_result,
  evidence_assessment, ...)`: **no LLM call.** By the time a signal
  reaches here, `aimfold_core/evidence/` has already done the
  interpretive work (Stage 1 always, Stage 2 if it qualified); scoring
  is a pure, deterministic weighted aggregation over that output —
  `AIMFOLD_MASTER_GOAL.md` section 28 (deterministic before AI) applied
  to the scoring step itself. Each dimension is computed by its own
  small function with an explicit formula (see the module docstring/
  source — e.g. Timing = 0.7×has_explicit_why_now + 0.3×recency-bucket),
  and honestly scores lower, with a visible rationale saying so, when
  only Stage 1 ran (no Stage-2 evidence to draw on).
- `tests/test_scoring.py` — 8 tests, all passing. One of them scores the
  *actual* Gemini output captured live while testing PR6 (not a synthetic
  fixture) — `total_score=91.8/100`, cleanly broken down per dimension —
  and a companion test confirms the same signal scores honestly lower
  (59.4) when only Stage 1 ran, with every affected dimension's rationale
  saying "No Stage-2 evaluation ran" rather than silently inflating the
  number.

**Deliberately not built in this PR:** a `scoring_versions` table letting
an Aim reference a specific, promotable, persisted weight-set. Section
22's observe→measure→propose→test→promote loop is what that table needs
to actually serve, and there's no learning/proposal engine yet to promote
anything through it (that's PR15) — so `SCORING_ENGINE_VERSION` is a
plain constant for now, same as `PROMPT_VERSION` was in `aim_compiler`/
`evidence` before either had anywhere to log to. `ScoringWeights` already
supports different weights per call/Aim type; wiring *which* weights a
given Aim uses into persisted config is that same future slice.

### `opportunity/` (PR8)

Clustering ("Entity → Opportunity → Signals",
`AIMFOLD_MASTER_GOAL.md` section 12) and the lifecycle state machine
(section 11), on top of the `opportunities` /  `opportunity_signals` /
`opportunity_entities` / `opportunity_lifecycle_events` tables added by
`supabase/migrations/20260819120500_opportunity_schema.sql`.

- `clustering.py` — `decide_cluster()`: entity identity is the hard
  clustering key. A new qualifying signal about an entity that already
  has a (non-`duplicate`/`invalid`) opportunity under the same Aim
  attaches to it — regardless of that opportunity's current lifecycle
  state — rather than spawning a new row; live-verified in Postgres:
  two signals for the same entity produced exactly one opportunity row
  with two linked signals, not two opportunities. Time proximity between
  signals is *not* an additional clustering gate (it's already captured
  as a confidence signal by `scoring`'s Timing dimension) — gating on it
  too would double-count the same information. If more than one eligible
  opportunity somehow exists for one entity, the function attaches to the
  most recently strengthened one and flags the rest in
  `other_eligible_opportunity_ids` rather than silently picking one.
- `lifecycle.py` — `next_lifecycle_state()`: a deterministic state
  machine over `discovered → evaluating → qualified → high_priority`,
  plus `stale`/`expired`/`revived` driven by score and days since the
  opportunity was last strengthened. It **never** touches `actioned`,
  `outcome`, `held`, `rejected`, `duplicate`, or `invalid` —
  `HUMAN_OR_ACTION_CONTROLLED_STATES` is checked first and those states
  are always returned unchanged, no matter the score — because
  `AIMFOLD_MASTER_GOAL.md` section 16 puts ambiguous opportunities,
  strategic decisions, and final decisions in human hands, not a
  re-scoring loop's. Verified directly: a score of 99 and 500 days of
  inactivity still leave an `actioned` opportunity `actioned`.
  `classify_momentum()` is the separate, *not persisted*, section-10
  descriptive label (`emerging`/`strengthening`/`weakening`/`stable`) for
  UI explanation — no score-history table exists yet to store it against.
- `mapping.py` — `opportunity_confidence_fields()`: reads `total_score`'s
  underlying `evidence_confidence` and `source_quality` dimensions off a
  PR7 `ExplainableScore` and turns them into the three separate
  `confidence` / `evidence_confidence` / `source_confidence` fields
  `AIMFOLD_MASTER_GOAL.md` section 9 lists. `confidence` is deliberately
  distinct from `total_score`: a low-scoring opportunity can still be a
  *confidently* low-scoring one.
- `tests/test_opportunity.py` — 12 tests, all passing.

**Deliberately not built in this PR:** no hard
`unique(tenant_id, aim_id, primary_entity_id)` constraint on
`opportunities` — section 12 says signals "should normally" strengthen
one opportunity, not "must always" (a long-closed opportunity and a
genuinely new later episode for the same company are both legitimate);
`clustering.py`'s soft, defensive handling is the actual invariant,
documented in the migration. No score-history table for
`classify_momentum()` to read real history from. No pipeline wiring —
same storage-agnostic limitation as PR4/PR6/PR7.

### `action/` (PR9)

The deterministic Action Recommender — `AIMFOLD_MASTER_GOAL.md` section
17 (Confidence-Based Automation) is already written as a threshold
policy, not a judgment call ("Low confidence → discard/hold... Very high
→ prepare recommended action automatically"), so **no LLM call happens
here either** — same "deterministic where deterministic works" reasoning
as `scoring/` and `opportunity/lifecycle.py`.

- `schema.py` — `ActionThresholds` (reuses `opportunity`'s
  qualified/high_priority score thresholds by convention, adds
  `very_high_confidence_threshold` as the extra gate between "surface it"
  and "auto-prepare it"), `ActionRecommendation` (action + `AutomationTier`
  + rationale).
- `recommender.py` — `recommend_action()`: maps
  `(total_score, confidence)` onto section 17's four tiers, and picks a
  specific action **only from the Aim's own `compiled_spec.likely_actions`**
  — it will never suggest an action the Aim didn't consider plausible
  (section 15). At the top tier it prefers a per-opportunity-type
  "primary" action (`contact` for customer_discovery, `apply` for
  career_discovery, etc.) but only if that action is actually in
  `likely_actions`, falling back to a conservative one otherwise — tested
  directly: an Aim listing `["monitor", "save"]` but not `"contact"`
  never recommends `"contact"`, even at maximum score and confidence.
  Also run against CollectIQ's real seeded Aim (`likely_actions:
  ["contact"]`) with the real score/confidence from PR7's live Gemini
  run (91.8 / 0.75) → correctly lands on `prepare_action_automatically` /
  `"contact"`.
- `tests/test_action.py` — 9 tests, all passing.

### `research/` (PR9)

The Research Agent (`AIMFOLD_MASTER_GOAL.md` section 39) — but scoped
honestly: **this is synthesis, not lookup.** No web-search or
third-party enrichment API is wired into this repo, so it can only
synthesize a coherent picture from what Aimfold has *already* observed
about an entity (attributes + the text of its own signals + prior
`entity_memory` notes) — never from outside knowledge a model might
otherwise "know" about a similarly-named real company.

- `schema.py` — `EntityContextSummary` (`key_facts`, `inferences`,
  `notable_changes`, `open_questions`, `summary`).
- `prompt.py` / `synthesizer.py` — same shape as
  `aimfold_core/evidence/evaluator.py`: `synthesize_entity_context()`
  calls the model, parses/validates, and — same anti-fabrication
  discipline as the Evidence Evaluator — verifies every `key_fact` is a
  literal substring of the concatenated source material before accepting
  the response, retrying with the validation error fed back on failure.
  Live-verified against real Gemini with two synthetic job postings for
  the same company: it correctly quoted three substantive facts (after a
  prompt fix — the first pass also "quoted" the entity-name/domain header
  lines back as facts; technically real substrings, just not useful, so
  the prompt now explicitly excludes them), kept its interpretation
  separately under `inferences`, and correctly left `notable_changes`
  empty rather than inventing a change neither posting actually showed.
  Also verified offline that a fabricated fact (an invented funding
  round) is rejected after exhausting retries.
- `tests/test_research.py` — 5 tests, all passing.

**Deliberately not built in this PR:** nothing wires `research/`'s
output back into `entity_memory` rows, or `action/`'s output into
`opportunities.recommended_action` — same storage-agnostic limitation as
every other `aimfold_core` module so far.

### `inbox/` (PR10)

The Opportunity Inbox — a static page (no build step), styled and
structured after `04_reviewer_dashboard/index.html` since that's this
repo's own working precedent for a Supabase-backed human approval queue.
Renders `AIMFOLD_MASTER_GOAL.md` section 47's four questions (Why this? /
Why now? / What proves it? / What next?) straight from `opportunities`
and its linked `signals`, with observed facts and AI inferences visibly
distinguished in the UI, not just enforced in backend validation. Approve
/ Hold / Reject write `opportunities.lifecycle_state` +
`opportunity_lifecycle_events`, locked down by
`20260819120700_opportunity_inbox_actions.sql`'s column-level GRANT + RLS
`WITH CHECK` — the first `aimfold_core` surface a human writes to
directly, every earlier table being select-only for `authenticated`.

Live-verified in an actual browser (not just read for syntax) against a
throwaway Docker Postgres+PostgREST stack with real seeded data,
including clicking through the real (unmodified) Supabase Auth login
flow and confirming both the UI state and the underlying Postgres rows
after Approve/Hold. That testing caught and fixed one real bug: a
duplicate `showApp()` call raced two `loadQueue()` fetches, leaving
`selected` pointing at a stale, discarded object so a successful DB
write didn't visibly update the sidebar until reload. See
`aimfold_core/inbox/README.md` for the full verification writeup,
including confirmation that the real, live Supabase project this page
points at by default does **not** have the Aimfold migrations applied
yet (a real `"Could not find the table 'public.opportunities'"` error,
not fabricated) — that's a decision to confirm with you, not something
done automatically.

### `feedback/` (PR11) + Inbox wiring

`AIMFOLD_MASTER_GOAL.md` section 18 ("Do not reduce all learning to
binary thumbs-up/down") and section 19 (Structured Rejection Reasons),
backed by `20260819120800_feedback_outcomes_schema.sql`'s `feedback` and
`outcomes` tables. Splits what section 18's combined list actually
contains into two things: `feedback` is the human's immediate decision
on an Opportunity (with a structured `rejection_reason` when rejected);
`outcomes` is a downstream real-world result (meeting, won, lost, ...)
usually recorded well after the fact.

- `schema.py` — `FeedbackRecord`/`OutcomeRecord`, with the same
  rejected-requires-a-reason invariant enforced here as the DB's
  `feedback_rejection_reason_required` CHECK constraint (defense in
  depth again). `tests/test_feedback.py` parses the migration file
  directly and asserts the Python `FeedbackType`/`RejectionReason`/
  `OutcomeType` literals match its check-constraint value lists
  exactly — same drift-check pattern as PR4's `CompiledAimSpec` test
  against the PR3 seed data.
- **The Opportunity Inbox now writes structured feedback, not just a
  lifecycle transition.** Approve/Hold/Reject each insert a `feedback`
  row alongside the existing `opportunities` update +
  `opportunity_lifecycle_events` insert from PR10, carrying a Learning
  Loop prediction snapshot (section 21: `predicted_total_score`,
  `predicted_confidence`, `predicted_recommended_action`,
  `predicted_lifecycle_state`, `scoring_version`) captured from `selected`
  *before* the write — so it reflects what was actually predicted at
  decision time even after a future rescoring pipeline changes the live
  opportunity. Reject reveals an 18-option structured reason picker
  (matching section 19's taxonomy exactly) and requires a selection
  before the write is allowed to proceed.
- Live-verified in the same real-browser/Docker/PostgREST setup as PR10:
  clicked Reject → picked "weak evidence" → Confirm reject, then
  confirmed via `psql` that the `feedback` row landed with
  `rejection_reason='weak_evidence'` and a correct prediction snapshot
  (`predicted_total_score=55`, `predicted_lifecycle_state='qualified'`);
  clicked Approve on the other opportunity and confirmed a second
  `feedback` row (`feedback_type='accepted'`, snapshot
  `predicted_total_score=91.8`, `predicted_recommended_action='contact'`).
  Also curl-verified the RLS/CHECK layer directly: inserting `feedback`
  with someone else's `user_id` → `403`; `feedback_type='rejected'` with
  no `rejection_reason` → `400` (CHECK constraint, not RLS — fires
  before RLS even gets a say); the legitimate combination → `201`.

**Deliberately not built in this PR:** nothing writes to `outcomes` yet
— no CRM/email/calendar integration exists in this environment to
source "meeting booked" or "won/lost" events from, so it's schema +
Python validation only, same storage-agnostic limitation as everywhere
else in `aimfold_core`. Nothing aggregates `feedback`/`outcomes` into
the Hierarchical Learning (section 20) or Learning Analytics picture
either — that's PR14's job, once there's enough real feedback to learn
from.

### `memory/` (PR12)

`AIMFOLD_MASTER_GOAL.md` section 26 (Aim Memory) and section 25 (Entity
Memory — the `entity_memory` table has existed since PR5, but nothing
wrote to it until now). No LLM call in the aggregation half of this
module — same "deterministic where deterministic works" reasoning as
`scoring/`, `opportunity/lifecycle.py`, and `action/`: turning
accumulated `feedback` rows into patterns is counting and averaging, not
interpretation.

- `aim_memory.py` — `compute_aim_memory(contexts)`: pure aggregation over
  a list of `FeedbackDecisionContext` (one per feedback row, already
  joined by the caller — storage-agnostic like everything else here).
  Produces `accepted_pattern`/`rejected_pattern` (average scoring-
  dimension values + rejection-reason breakdown), `successful_action`/
  `failed_action` (which `recommended_action` got accepted vs rejected),
  `preferred_entity_attribute`, and `source_effectiveness`
  (per-`source_key` acceptance rate). Every function returns nothing for
  a category it can't actually support from the data given, rather than
  padding a payload with zeros — verified directly:
  `compute_aim_memory([])` returns `[]`, and a context set with no
  `source_keys` anywhere produces no `source_effectiveness` entry.
- **`learned_exclusion` is the one derived *suggestion*, not just a
  statistic** — it only fires when a *structural* rejection reason
  (`wrong_geography`, `too_small`, `wrong_entity_type`, ...; explicitly
  not situational ones like `poor_timing` or `duplicate`) accounts for
  more than half of at least 3 rejections. Tested all three guardrails
  independently: a dominant *situational* reason never fires it even at
  100% of rejections; 2 samples isn't enough even at 100%; a payload
  explicitly says `"not applied automatically"` — this is a candidate
  for a human to add to `compiled_spec.exclusions`, not something that
  silently narrows an Aim on its own (section 22: proposals require
  approval).
- `entity_memory.py` — `build_entity_memory_row()`: the missing link
  from PR9's `synthesize_entity_context()` output to an actual insertable
  `entity_memory` row (`memory_type='research_synthesis'`).
- `tests/test_memory.py` — 10 tests, all passing, including a migration
  cross-check (same pattern as PR11) confirming `MemoryType` matches
  `aim_memory`'s check constraint exactly.

Live-verified in Docker: inserted two successive `aim_memory` snapshots
for the same `(aim_id, memory_type)` and confirmed the "current picture"
query (`distinct on (aim_id, memory_type) ... order by computed_at desc`)
correctly returns only the latest one while the earlier snapshot stays in
the table — the append-only-history design actually behaves as intended,
not just on paper. RLS: outsider sees 0 rows, the real tenant member sees
what was inserted, and a direct `authenticated` insert is correctly
rejected (this table has no insert policy — populated by an analytics
job via service-role, same as `entity_memory`).

**Deliberately not built in this PR:** nothing runs
`compute_aim_memory()` on a schedule or writes its output to
`aim_memory` — no job/cron infrastructure exists in this environment,
and periodic recomputation is really PR14's (Learning Analytics) job
once there's enough real feedback volume to make it worth automating.

### `evaluation/` (PR13)

`AIMFOLD_MASTER_GOAL.md` section 29 (Evaluation Framework) and section
30 (Regression Protection) — a labeled dataset run through the *real*
pipeline (`extract_stage1_evidence` → `evaluate_evidence` →
`score_signal` → `recommend_action`, the exact same functions PR6/PR7/
PR9 ship, not a simulation of them), scored against hand-authored
expectations.

**Scope note:** section 29 also lists "stale opportunities, revived
opportunities, multi-signal opportunities" — those describe *temporal
sequences* of signals, not one signal's evidence quality, and are
already covered by `aimfold_core/opportunity/tests/test_opportunity.py`
(staleness/revival/clustering). Duplicating them here as static labeled
examples would mean faking a dataset for something this framework can't
actually evaluate from one signal's text. `dataset.py` covers the five
categories that are: `excellent`, `acceptable`, `false_positive`,
`irrelevant_signal`, `ambiguous`.

- `dataset.py` — `COLLECTIQ_EVAL_V1`, 6 examples. Every `signal_text` is
  either a real example already live-verified in an earlier PR (the
  `excellent-ar-analyst-acme` case is the exact text Gemini scored 91.8
  on in PR7/PR9/PR11), or purpose-built for a specific known edge case.
  The standout is `false-positive-ar-vr-engineer`: a real Stage-1 blind
  spot, deliberately included — the `\bAR\b` regex (from "AR hiring")
  matches "AR/VR" as a standalone word, and the text separately mentions
  "spreadsheets," "high volume," and "reporting" in an unrelated
  (software project tracking) context, so Stage 1 alone scores it 60/100
  and wrongly qualifies it. The example exists specifically to prove
  Stage 2 catches what Stage 1 can't.
- `runner.py` — `run_evaluation(examples, compiled_spec, llm_client)`
  computes `precision`, `false_positive_rate`,
  `accepted_opportunity_rate`, `ranking_quality` (pairwise rank
  concordance between expected category and actual `total_score`, no
  scipy dependency), and — only when `llm_client` is given (Stage 2 ran)
  — `calibration_accuracy`, `evidence_grounding_accuracy`,
  `action_recommendation_quality`. `llm_client=None` runs Stage 1 only:
  free, deterministic, fast enough to be a pre-commit sanity check.
  **`precision` is measured at the real Stage-1 gate** (the actual
  threshold that routes a signal to Stage 2 in production), not the
  final score — so it's honestly imperfect (0.75, both offline-stub and
  live) rather than papering over Stage 1's real false-positive rate
  with Stage 2's correction.
- `regression.py` — `compare_eval_reports(baseline, candidate)`: flags
  any metric that got worse beyond a tolerance (default 5%), plus a
  per-category average-score breakdown (section 30's "check regressions
  across... high-value examples, edge cases" — category is the
  available breakdown axis here; breaking down by Aim type/tenant/
  geography needs the second/third validation Aim from PR16/17 to have
  anything to compare against).
- `tests/test_evaluation.py` — 5 tests, fully offline (`StubLLMClient`,
  no API cost), all passing.

**A real bug caught while building the offline tests, not a synthetic
one:** the grounding check originally treated an empty
`expected_matched_criteria` as "nothing to check," when for the false-
positive example an empty list is the whole point — a correct Stage-2
assessment should find *zero* matching criteria there. Fixed to branch
on intent (recall-check when criteria are expected, "found nothing"
check when none are) rather than skipping the check whenever the list
happened to be empty.

**Live-verified against real Gemini** (`gemini-flash-lite-latest`), not
just the offline stub — every single check passed, and the numbers
matched the offline stub's predictions closely enough to trust the stub
suite going forward:

| metric | value |
|---|---|
| precision | 0.75 |
| false_positive_rate | 0.333 |
| accepted_opportunity_rate | 1.0 |
| ranking_quality | 0.923 |
| calibration_accuracy | 1.0 |
| evidence_grounding_accuracy | 1.0 |
| action_recommendation_quality | 1.0 |

The false-positive case specifically: Stage 1 scored it 60/100 and
wrongly qualified it (as designed); the real model's Stage-2 assessment
found `matched_positive_criteria: []` and correctly recognized the "AR"
match was augmented reality, not accounts receivable — `total_score`
dropped to 36.1. Also caught and fixed a dataset calibration error this
way (not a code bug): `excellent-ar-manager-full-cycle` initially had
`expected_score_range=(85, 100)`, a naive guess; the real engine scores
it ~71-72, because that text has no explicit timing trigger and Timing/
Trigger Strength is 20% of the total — evidence completeness alone
doesn't guarantee a top-tier score, a genuine property of the scoring
engine worth having on record, not something to paper over by loosening
the range without explanation (see the note in `dataset.py`).

**Deliberately not built in this PR:** nothing runs this on a schedule
or gates a deploy on it — no CI infrastructure exists in this
environment to wire that into. `compare_eval_reports()` is ready to be
called by hand (or by a future CI step) whenever a prompt/scoring/signal
change is made, per section 29's instruction.

### `analytics/` (PR14)

`AIMFOLD_MASTER_GOAL.md` section 24 (Performance Learning) and section
20 (Hierarchical Learning: Global / Opportunity-Type / Organization /
Aim). No LLM call, same reasoning as `memory/`: this is counting and
averaging, not interpretation. Distinct from `memory/` on purpose —
`memory/` produces *inputs* that feed back into one Aim's future
scoring/exclusions (PR12, section 26); `analytics/` produces *outputs*
for human observability (funnel counts, outcome correlation, economic
totals) and never feeds back into automated behavior itself.

- `performance.py` — `compute_performance_report()`: raw signal count →
  qualified → surfaced opportunities → accepted/rejected/held, plus (new
  in this PR — `memory/`'s PR12 aggregation never touched `outcomes`)
  correlating each opportunity's feedback decision with whatever real
  `outcomes` were eventually recorded against it (`successful_outcome_rate`
  vs `unsuccessful_outcome_rate`, with `custom` deliberately left
  unclassified rather than guessed), and an economic summary from
  `outcomes.monetary_value`. Section 24 also asks for "cost per accepted
  opportunity" / "cost per successful outcome" — **not computed**, since
  no cost/spend tracking exists anywhere yet (that's PR18, Production
  observability and cost tracking); fabricating a cost number with
  nothing to compute it from would violate the same no-fabrication
  discipline the evidence/research modules enforce.
- `rollup()` — groups a list of per-opportunity contexts by `aim`,
  `tenant`, or `opportunity_type`. **The tenant-isolation boundary is
  explicit and load-bearing, not incidental**: `aim`/`tenant` rollups are
  isolated by construction (an Aim belongs to exactly one tenant) —
  verified directly by a test that feeds `rollup()` a mixed batch from
  two tenants and confirms tenant A's accepted count never leaks into
  tenant B's aim report. `opportunity_type` rollup *deliberately*
  aggregates across every tenant given to it (a cross-tenant benchmark:
  "how does customer_discovery perform across everyone using it") and
  says so in the returned report's `note` field — but nothing in this
  module or `memory/` ever reads that cross-tenant report back into a
  single tenant's behavior; only aim-scoped Aim Memory does that.
  `rollup(level='global')` is refused outright (raises, points the
  caller at `compute_performance_report()` directly) rather than
  silently being just another grouping that's easy to misuse.
- `tests/test_analytics.py` — 9 tests, all passing.

**Deliberately not built in this PR:** nothing queries the database to
build `OpportunityOutcomeContext` rows or calls this on a schedule — same
storage-agnostic, no-cron-infrastructure limitation as `memory/`. No new
migration either; like `evaluation/` (PR13), this is a pure computation
layer with nowhere new to persist to.

### `proposals/` (PR15)

`AIMFOLD_MASTER_GOAL.md` section 22 (Safe Self-Improvement): Observe →
Measure → Propose → Test → Promote, "Aimfold must not freely rewrite
production behavior." Ties PR12 (Aim Memory), PR13 (evaluation), and PR7
(scoring) together into an actual proposal lifecycle — nothing here is
ever auto-applied.

- `generator.py` — two proposal types, both deterministic (no LLM):
  - `propose_exclusion()` turns a `learned_exclusion` Aim Memory entry
    into a candidate `compiled_spec` with the exclusion added. **Honest
    about a real limitation**: no exclusion-matching logic exists yet in
    `aimfold_core/evidence` or `aimfold_core/scoring` (the `excluded`
    flag `score_signal()` takes is caller-supplied, not derived from
    `compiled_spec.exclusions`) — the proposal's `expected_impact` says
    so explicitly rather than implying approval closes the loop.
  - `propose_scoring_weight_adjustment()` compares average per-dimension
    scores between `accepted_pattern`/`rejected_pattern` Aim Memory
    entries and, only above a minimum sample size, proposes a small
    (±2 point) shift toward whichever dimension most separates accepted
    from rejected opportunities. This one *is* fully closed-loop —
    `score_signal()` already takes a real `weights` parameter.
- `testing.py` — the "Test" step, via PR13's evaluation framework.
  **`test_scoring_weight_proposal()` makes zero LLM calls** — it calls
  PR13's `rescore_with_weights()`, which reuses already-gathered
  Stage-1/Stage-2 evidence from a prior evaluation run (PR13's
  `EvalResult` was extended in this PR to cache the raw
  `Stage1EvidenceResult`/`EvidenceAssessment` objects specifically for
  this) and only recomputes the final score. Directly implements
  `AIMFOLD_MASTER_GOAL.md`'s newly-added "Persist before expensive next
  steps" engineering rule rather than just citing it — proven by the
  function's own signature (no `llm_client` parameter exists to call).
  `test_exclusion_proposal()` changes `compiled_spec` itself, which
  Stage 1 output depends on, so it can't skip re-running the pipeline
  the same way — but still accepts `llm_client=None` to test only the
  free, deterministic Stage-1 qualification labels.
- `schema.py` — `LearningProposal` matches section 22's required-fields
  list exactly (current/proposed behavior, supporting observations,
  affected Aims, sample size, expected impact, evaluation results,
  possible regressions, rollback path), with the same "exactly one
  candidate matching proposal_type" validator as the DB's CHECK
  constraint.
- `tests/test_proposals.py` — 8 tests, all passing, including one true
  end-to-end integration test: a real PR13 evaluation run → real
  `compute_aim_memory()` (PR12) on decisions derived from it → a real
  generated proposal → tested via `testing.py` — not three isolated unit
  tests stitched together in the write-up only.

**A real, previously-shipped security gap found and fixed while
building this** (not a PR15-only issue): `PR10`'s
`opportunities.lifecycle_state` column-scoped `GRANT` had the same flaw
`learning_proposals`' new grant would have had — a column-level `GRANT`
doesn't narrow a broader privilege already in effect, and Supabase
grants `authenticated` table-wide privileges by default. Confirmed live,
not assumed: without an explicit `REVOKE UPDATE` first, `authenticated`
could still write `opportunities.total_score` in the very same request
that legitimately updated `lifecycle_state` — the RLS policy never even
saw it, since it only inspects `lifecycle_state`'s value. Fixed in both
`20260819120700_opportunity_inbox_actions.sql` (retroactively — that
migration was already committed and pushed) and the new
`20260819121000_learning_proposals_schema.sql`; re-verified live that
the same smuggling attempt is now rejected with a real permission error
on both tables, and that the legitimate single-column update still
works. See `supabase/README.md`'s new convention entry.

**Deliberately not built in this PR:** nothing calls `generator.py` or
`testing.py` on a schedule, and nothing implements the actual "Promote"
step (writing a new `aim_versions` or `scoring_versions` row and
flipping `is_current`) — that's a real Supabase write, held per the same
storage-agnostic pattern as every other `aimfold_core` module, and
because promotion is explicitly meant to require a human `approved`
decision first (verified live: `authenticated` can move a proposal's
`status` to `approved`/`rejected` but not `promoted` — only
`service_role` can do that).

### Horizontal Validation, Aim #2 (PR16)

`AIMFOLD_MASTER_GOAL.md` section 41: *"Aimfold is not considered
successfully generalized until materially different Aims operate on the
same core engine without changing engine code."* PR16 is that test, not
new capability — **the actual deliverable is that this PR touches zero
files under `aimfold_core/*.py`**. Everything is data: one new migration
(`20260819121100_seed_career_discovery_aim.sql`) and one new evaluation
dataset (`aimfold_core/evaluation/dataset_career_discovery.py`).

- **The compiled Aim is not hand-authored.** It's the real, live,
  unedited output of the unmodified PR4 Aim Compiler
  (`gemini-flash-lite-latest`) given `AIMFOLD_MASTER_GOAL.md` section 3's
  own Career Aim example verbatim: *"Find finance/data roles where my
  finance transformation background creates an unusual advantage."*
  Editing the compiler's output by hand to make it "better" would have
  defeated the entire point of this PR — it would prove I can special-
  case the engine for a second domain, not that the engine generalizes.
- **Materially different by every axis section 41 names**, confirmed
  live in Postgres, not just asserted: `target_entity_types = ["job",
  "employer"]` (CollectIQ: `["company"]`), `opportunity_type =
  'career_discovery'`, `likely_actions = ["apply", "research", "save"]`
  (CollectIQ: `["contact"]`), and — checked directly — **zero overlapping
  scoring_weights labels** between the two Aims (CollectIQ:
  `AR hiring, collections/credit control, ageing, ...`; Career:
  `Finance transformation focus, Systems and process modernization,
  Data and analytics integration`).
- **Reuses the same two source connectors** (`linkedin_jobs_apify`,
  `indeed_jobs_apify`) CollectIQ already uses, with career-relevant
  search keywords — proving connector reuse across domains, not just the
  compiler/evidence/scoring layers.
- **Ran the identical, unmodified pipeline live** — a second 5-example
  labeled dataset (`CAREER_DISCOVERY_EVAL_V1`, same five evaluable
  categories as PR13's dataset) through `run_evaluation()` exactly as
  written, no branch or special case for this Aim anywhere in the call
  path. Stage 1 qualification predictions were correct for all 5 before
  any live call (free, deterministic); the live Gemini run then produced
  `calibration_accuracy=0.667`, `evidence_grounding_accuracy=0.667`.
- **A real, disclosed limitation surfaced by this run, not hidden**: the
  dataset's false-positive example (a marketing-analytics posting that
  coincidentally uses finance-transformation-adjacent language) was
  *not* cleanly rejected the way PR13's AR/VR false positive was —
  Stage 2 matched 2 of 3 positive_criteria and scored it 58.6/100
  despite Gemini's own explanation noting the role sits in "a marketing
  context rather than a finance department." Root cause: this Aim's
  Compiler-generated `positive_criteria` are worded more abstractly than
  CollectIQ's crisp, AR-specific ones, giving Stage 2 more room to credit
  a topically-adjacent-but-wrong-domain posting. The dataset's expected
  values were **not** loosened to hide this — see
  `dataset_career_discovery.py`'s notes on that example. The right fix is
  a `learning_proposal` (PR15) refining this Aim's wording later, not
  hand-editing the Compiler's output now.
- **Tenant isolation confirmed live across the two Aims specifically**
  (not just in the abstract): seeded Aim #2 under a distinct tenant
  (clearly labeled `career-discovery-validation`, not disguised as a
  real customer) and confirmed an authenticated member of that tenant
  sees only their own Aim — CollectIQ's is invisible to them, and vice
  versa.

### Horizontal Validation, Aim #3 (PR17)

`AIMFOLD_MASTER_GOAL.md` section 41 requires **three** materially
different Aims — PR17 is the third, closing out the section's minimum
requirement (Aim 1 = CollectIQ, PR3; Aim 2 = Career Discovery, PR16).
Same discipline as PR16: **zero files under `aimfold_core/*.py` touched**
to produce this. Everything is data — two new migrations
(`20260819121200_sources_planned_status.sql`,
`20260819121300_seed_funding_discovery_aim.sql`) and one new evaluation
dataset (`aimfold_core/evaluation/dataset_funding_discovery.py`).

- **The compiled Aim is not hand-authored**, same as PR16: the real,
  live, unedited output of the unmodified PR4 Aim Compiler
  (`gemini-flash-lite-latest`) given `AIMFOLD_MASTER_GOAL.md` section 3's
  own Funding Aim example verbatim: *"Find active grants relevant to
  climate-health infrastructure in emerging markets."*
- **Materially different by every axis section 41 names, and different
  from both prior Aims, not just CollectIQ**: `opportunity_type =
  'funding_discovery'` (CollectIQ: `customer_discovery`; Career:
  `career_discovery`), `target_entity_types = ["grant", "funding_program",
  "organization"]` (not `["company"]` or `["job", "employer"]`),
  `likely_actions = ["review_eligibility", "prepare_application", "apply",
  "save"]` (a four-action set overlapping Career's `apply`/`save` but
  adding two funding-specific actions neither other Aim uses),
  `confidence_thresholds.qualified_signal_min_score = 70` — meaningfully
  higher than CollectIQ's 60 and Career's 40, live-confirmed to actually
  gate qualification differently (a single scoring_weights keyword hit,
  40 points, can never qualify this Aim on its own the way it could
  qualify Career at the same score). Checked directly in Postgres: **zero
  overlapping scoring_weights labels across all three Aims** (17 distinct
  labels total across CollectIQ's 11, Career's 3, and Funding's 3).
- **A new, honestly-registered `sources` connector.** Unlike PR16 (which
  reused CollectIQ's existing job-board connectors), Funding Discovery
  needs a grant-database connector this repo has never had — no Apify
  actor for grant listings exists, and one was not fabricated just to
  populate this seed. `20260819121200_sources_planned_status.sql` adds a
  `'planned'` value to `sources.status` (previously
  `active`/`disabled`/`deprecated`, none of which honestly describe "in
  the catalog, no working implementation yet") specifically so
  `grants_database_web_search` could be registered truthfully rather than
  mislabeled `'disabled'` (which would imply it once worked). Directly
  applies the "Filter before paid acquisition" / "Qualify before
  expensive enrichment" rules in `AIMFOLD_MASTER_GOAL.md`'s Pipeline Cost
  & Evidence Discipline section: the Aim's structure, scoring, and
  evaluation are validated *before* any paid connector is wired up, not
  after. The three signal hypotheses registered against it are marked
  `is_experimental = true` for the same reason — they describe what this
  Aim expects to see once the connector exists, not signals actually
  observed yet.
- **Ran the identical, unmodified pipeline live** — a third 5-example
  labeled dataset (`FUNDING_DISCOVERY_EVAL_V1`, same five evaluable
  categories as PR13/PR16's datasets) through `run_evaluation()` exactly
  as written, no branch or special case for this Aim anywhere in the call
  path. Stage 1 qualification predictions were correct for all 5 before
  any live call. Multiple live Gemini runs during calibration showed real
  run-to-run variance on the borderline "acceptable" example (total_score
  ranged 62.6–85.35 across four separate live calls) — the dataset's
  score range was deliberately widened to (45, 95) to absorb this rather
  than pinned to one observed run, which would have made the offline
  regression check flaky for reasons that have nothing to do with the
  engine being wrong.
- **A different outcome than PR16's disclosed limitation, also surfaced
  honestly, not hidden**: PR16's Career Discovery false-positive example
  (marketing-analytics posting) was *not* cleanly caught by Stage 2 —
  this Aim's structurally analogous false-positive example (a domestic,
  non-climate hospital-equipment grant, chosen specifically to test the
  same Stage-1 keyword-blind-spot) *was*: Stage 2 scored it 45.1/100,
  well below the 70-point acceptable threshold, and correctly matched
  only the one `positive_criteria` entry that's actually true, correctly
  declining the other two. Documented in `dataset_funding_discovery.py`'s
  notes as the more interesting result it actually is: this Aim's
  Compiler-generated criteria are worded narrowly enough (each maps to a
  single checkable fact) that Stage 2 recovers from Stage 1's blind spot
  cleanly, in contrast to Career Discovery's more abstractly-worded
  criteria which let a comparable false positive through. Neither
  disclosure was cherry-picked after the fact — both dataset files
  documented an expectation *before* the live run and reported what
  actually happened against it.
- **Tenant isolation confirmed live across all three Aims**: seeded Aim
  #3 under a distinct, clearly-labeled tenant
  (`funding-discovery-validation`, not disguised as a real customer) and
  confirmed an authenticated member of that tenant sees only their own
  Aim — neither CollectIQ's nor Career Discovery's are visible to them.

### `observability/` (PR18)

`AIMFOLD_MASTER_GOAL.md` section 34 (Observability) and section 35 (Cost
Intelligence). Scoped tightly to what's actually instrumentable today —
see `20260819121400_observability_schema.sql`'s header for why the
broader operational telemetry those sections also name (source connector
health, retries, queue sizes, scheduled-workflow tracking) is
deliberately not built yet: none of that infrastructure exists in this
repo, and fabricating tables for it would mean nothing real ever
populates them.

- **`instrumented_client.py` — `InstrumentedLLMClient`.** Wraps any real
  `LLMClient` and implements the identical interface, so it drops into
  `compile_aim()`, `evaluate_evidence()`, and `synthesize_entity_context()`
  with **zero changes to those three modules** — each already depends
  only on the abstract `LLMClient.complete()` contract (section 27, Model
  Independence). Records one `ModelRun` per call, success or failure,
  with self-measured wall-clock latency (LLMResponse.latency_ms is never
  actually populated by either concrete provider client, so this
  instruments it independently rather than trusting an unset field).
- **`cost.py` — `estimate_model_cost()`.** A hardcoded `(provider,
  model) -> TokenRate` table, checked 2026-08-20 against public pricing
  pages for the three models this codebase actually uses
  (`gemini-flash-lite-latest`, `gemini-flash-latest`,
  `claude-sonnet-5`). Returns `None`, never a guess, for any
  unrecognized model or missing token count — and the file's own
  docstring flags that Google has already announced retiring the Gemini
  2.5 line on 2026-10-16, after which the `-latest` aliases this table is
  keyed on will silently point at different (and differently priced)
  models. Live-verified: wrapped a real `GeminiLLMClient` call through a
  real `compile_aim()` invocation and confirmed the recorded
  `estimated_cost_usd` matches the rate-table formula exactly against the
  real token counts Gemini returned (2122 in / 565 out → $0.0004382).
- **`workflow_tracking.py` — `WorkflowRunTracker`.** A context manager,
  not a decorator — wraps a *call site*, so the multi-step computations
  it tracks stay unmodified. `workflow_type` is deliberately narrow
  (`evaluation_run`, `proposal_test`, `aim_memory_recompute`): the three
  multi-item batch computations that already run as one coherent unit
  today (`run_evaluation()`, PR15's `test_*_proposal()`,
  `compute_aim_memory()`). An exception inside the `with` block is
  recorded as a `'failed'` WorkflowRun (with the error message) and then
  re-raised — this class observes, it never swallows failures.
  Live-verified wrapping a real `run_evaluation()` call.
- **`cost_analytics.py`** — section 35's four cost metrics (cost per Aim,
  per surfaced Opportunity, per accepted Opportunity, per successful
  Outcome), mirroring `analytics/performance.py`'s (PR14) storage-agnostic
  rollup design: `CostContext` is a caller-joined, already-summed-per-Aim
  input (the natural cost-attribution unit — one Aim belongs to exactly
  one tenant, so per-aim/per-tenant rollups are isolated by construction);
  `rollup()` groups many Aims' contexts up to `tenant`/`opportunity_type`/
  `global`, with the same explicit "opportunity_type and global
  deliberately cross tenants, as a benchmark, never fed back into one
  tenant's behavior" boundary PR14 draws. Ratios return `None`, not
  `0.0` or a `ZeroDivisionError`, when a funnel stage has zero items —
  and unpriced model calls are counted and surfaced in the report's
  `note`, never silently treated as free.
- `schema.py` — `ModelRun`/`WorkflowRun` pydantic models mirroring
  `model_runs`/`workflow_runs` exactly; `WorkflowRun` has a validator
  enforcing `duration_ms` is set if and only if `status != 'running'`
  (can't know a duration before something finishes).
- `tests/test_observability.py` — 17 tests: DB CHECK-constraint
  cross-checks for both Literal types (same pattern as PR12's
  `MemoryType` test), cost-table arithmetic and its `None`-not-0.0
  guarantees, `InstrumentedLLMClient`'s success/failure paths (using
  `StubLLMClient` so this suite stays offline), `WorkflowRun`'s
  duration/status invariant, `WorkflowRunTracker`'s success/failure
  paths, and `cost_analytics`' tenant-isolation rollup tests (directly
  mirroring PR14's `test_rollup_by_aim_never_mixes_tenants`).

**Deliberately not built in this PR:** nothing calls `InstrumentedLLMClient`
or `WorkflowRunTracker` from the actual `aim_compiler`/`evidence`/
`research`/`evaluation`/`proposals`/`memory` call sites yet — wiring
every real invocation throughout this codebase to construct an
instrumented client and persist its `model_runs`/`workflow_runs` rows
back to Supabase is a real, meaningful follow-up, held to the same
storage-agnostic pattern (and same "verify the primitive live before
wiring it everywhere" discipline) as every other module in this
sequence. `prompt_versions`/`connector_versions`/`experiments` (named in
section 36's domain list) are not built — nothing versions prompts or
connectors independently of the plain text columns that already carry
that information (`aim_versions.compiler_prompt_version`,
`sources.connector_version`), and nothing runs A/B experiments yet.

### Security and multi-tenant hardening (PR19)

Pure SQL/RLS — no new `aimfold_core` Python module. Full detail lives in
`supabase/README.md`'s "Security audit findings" section:
`20260819121500_security_hardening.sql` fixes three real gaps found by
systematically auditing every RLS policy shipped PR1-18 (a `tenant_members`
privilege-escalation path to `'owner'`, `learning_proposals` decision-
attribution spoofing, and `feedback`/`outcomes` cross-tenant `opportunity_id`/
`aim_id` reassignment), and wires up `audit_log` — schema-only since PR1,
never previously populated — via two `SECURITY DEFINER` triggers. Every
finding was confirmed live with a real attack-scenario test (Postgres
roles, not SQL inspection) both before the fix (attack succeeds) and
after (attack rejected, legitimate use unaffected).

### Deployment (PR20)

Also pure documentation/tooling, no new Python module — see
[`DEPLOYMENT.md`](../DEPLOYMENT.md) at the repo root for environments,
deployment instructions, health checks, rollback procedures, a release
checklist, and an honest section-43 MVP-readiness self-assessment (12 of
18 criteria met, 4 partial, 2 not met — the two gaps are both "nothing
in this codebase runs automatically yet," i.e. no scheduler/retry
mechanism, which is the actual blocker to a real release, not schema or
RLS completeness). Nothing has been applied to the real production
Supabase project.

## Running the test suites

```bash
cd aimfold_core
pip install -r aim_compiler/requirements.txt   # pydantic + fastapi; anthropic/google-genai only needed for live use
python aim_compiler/tests/test_compiler.py
python evidence/tests/test_evidence.py
python scoring/tests/test_scoring.py
python opportunity/tests/test_opportunity.py
python action/tests/test_action.py
python research/tests/test_research.py
python feedback/tests/test_feedback.py
python memory/tests/test_memory.py
python evaluation/tests/test_evaluation.py
python analytics/tests/test_analytics.py
python proposals/tests/test_proposals.py
python observability/tests/test_observability.py
```

## Running the API locally (schema validation only, no live compilation)

```bash
cd aimfold_core/aim_compiler
uvicorn api:app --reload --port 8001
curl -s localhost:8001/health
```

`POST /aims/compile` returns `503` if neither `ANTHROPIC_API_KEY` nor
`GEMINI_API_KEY` (+ `AI_PROVIDER=gemini`) is set.
