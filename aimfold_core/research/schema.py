"""Research Agent output — AIMFOLD_MASTER_GOAL.md section 39 ("Research
adds company context") and section 25 (Persistent Entity Memory: "a new
signal should be interpreted in context rather than independently").

This is a SYNTHESIS task, not a fetch task: no web-search or third-party
enrichment API is wired into this repo, so the Research Agent can only
work from what Aimfold has already observed about an entity (its
attributes, the text of its own signals, and prior entity_memory notes) —
never from outside knowledge the model happens to know. Same
Evidence-First discipline as aimfold_core/evidence applies here, in code,
not just in the prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityContextSummary(BaseModel):
    key_facts: list[str] = Field(
        ...,
        min_length=1,
        description="Quoted verbatim from the provided source material (entity attributes + signal texts + prior memory notes). synthesizer.py verifies each one is a literal substring.",
    )
    inferences: list[str] = Field(
        default_factory=list,
        description="The model's synthesis/interpretation across the key_facts — clearly separate from them, never presented as directly observed.",
    )
    notable_changes: list[str] = Field(
        default_factory=list,
        description="Specific things that appear to have changed over time, if the provided material shows a change (e.g. a new signal contradicts or extends an older one). Empty if there's only one data point.",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="What Aimfold does NOT know yet about this entity that would sharpen future scoring — an honest gaps list, not filled in with guesses.",
    )
    summary: str = Field(..., min_length=1, description="A short plain-language synthesis for display, grounded only in key_facts/inferences above.")

    model_config = {"extra": "forbid"}


class ResearchResult(BaseModel):
    context: EntityContextSummary
    researcher_model: str
    researcher_prompt_version: str
