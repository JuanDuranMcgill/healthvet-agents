"""Query planning: expand a vendor + goals/directives into targeted sub-queries.

Uses the shared ``make_llm()`` factory to expand queries. If the LLM call fails
the engine must still run, so it falls back to a templated query set and logs the
fallback. It never pretends a failed plan succeeded.
"""
from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable

logger = logging.getLogger("research.planner")

# expander signature: async (vendor, goals, gap_directives) -> list[str] | None
Expander = Callable[[str, list[str], list[str]], Awaitable[list[str] | None]]


class QueryPlanner:
    def __init__(self, expander: Expander | None = None):
        self._expander = expander

    async def plan(
        self,
        vendor: str,
        goals: list[str] | None = None,
        gap_directives: list[str] | None = None,
    ) -> list[str]:
        goals = list(goals or [])
        gap_directives = list(gap_directives or [])
        fallback = self._templated(vendor, goals, gap_directives)
        expander = self._expander or _llm_expander
        try:
            expanded = await expander(vendor, goals, gap_directives)
            if expanded:
                return list(expanded)
        except Exception as exc:  # noqa: BLE001 - any LLM failure must not abort
            logger.warning("query planner LLM failed (%s); using templated fallback", exc)
        return fallback

    @staticmethod
    def _templated(vendor: str, goals: list[str], gap_directives: list[str]) -> list[str]:
        # Scoped re-investigation: only the directive queries, never a full sweep.
        if gap_directives:
            return [f"{vendor} {directive}" for directive in gap_directives]
        queries = [
            f"{vendor} healthcare customer references case studies",
            f"{vendor} lawsuit regulatory violation negative news",
            f"{vendor} health system implementation",
            f"{vendor} HIPAA data breach OCR notification",
        ]
        queries.extend(f"{vendor} {goal}" for goal in goals)
        return queries


_EXPANSION_PROMPT = (
    "You plan web search queries for healthcare vendor due diligence. "
    "Given a vendor and goals, return a JSON array of 4-8 specific search query "
    "strings (no prose, JSON array only). Vendor: {vendor}\nGoals: {goals}\n"
    "Gap directives: {directives}"
)


async def _llm_expander(vendor: str, goals: list[str], gap_directives: list[str]) -> list[str] | None:
    """Default expander backed by the shared LLM factory (imported lazily)."""
    from langchain_core.messages import HumanMessage

    from agents.llm import make_llm

    llm = make_llm("gpt-4o-mini")
    prompt = _EXPANSION_PROMPT.format(
        vendor=vendor,
        goals="; ".join(goals) or "general due diligence",
        directives="; ".join(gap_directives) or "none",
    )
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    content = (resp.content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("[") :]
    queries = json.loads(content)
    if isinstance(queries, list):
        return [str(q) for q in queries if str(q).strip()]
    return None
