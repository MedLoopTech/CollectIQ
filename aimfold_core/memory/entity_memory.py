"""Formats a Research Agent result (PR9) into an entity_memory row shape
(PR5's table). Thin on purpose — entity_memory already accepts arbitrary
memory_type/payload; this just gives the research -> memory link a
single, tested, canonical form instead of every caller inventing its own.
"""

from __future__ import annotations

from aimfold_core.research.schema import ResearchResult


def build_entity_memory_row(result: ResearchResult) -> dict:
    """Returns a dict matching entity_memory's insertable columns
    (minus id/tenant_id/entity_id/created_at, which the caller already
    knows and this module doesn't). memory_type='research_synthesis' —
    not one of aim_memory's ten section-26 categories, since this is
    section 25 (Entity Memory), a different concept with its own table."""

    return {
        "memory_type": "research_synthesis",
        "payload": {
            "key_facts": result.context.key_facts,
            "inferences": result.context.inferences,
            "notable_changes": result.context.notable_changes,
            "open_questions": result.context.open_questions,
            "summary": result.context.summary,
            "researcher_model": result.researcher_model,
            "researcher_prompt_version": result.researcher_prompt_version,
        },
    }


__all__ = ["build_entity_memory_row"]
