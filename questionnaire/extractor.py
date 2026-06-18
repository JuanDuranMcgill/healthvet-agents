"""
Extractor: one LLM call turns the agents' free-text findings into structured,
per-category vendor scores (0-10), detected deal-breaker flags, and a list of
"uncovered" material factors the profile's categories don't capture.

The LLM only *reads evidence and scores it* — it never sets profile weights.
Output is validated against the known category keys before use.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from .categories import CATEGORY_KEYS

EXTRACT_SYSTEM = """You are an evidence extractor for a healthcare vendor vetting pipeline.

You are given the combined free-text findings of several specialist agents about
ONE vendor. Convert them into a strict JSON object. Do NOT invent evidence; if a
category has no supporting evidence, score it 5 (neutral) with confidence 0.

Score each of these categories from 0 (terrible / disqualifying) to 10 (excellent):
{categories}

Return ONLY a JSON object of this exact shape:
{{
  "vendor": "<vendor name>",
  "scores": {{
    "<category_key>": {{"score": <0-10 int>, "evidence": "<short quote/summary>", "confidence": <0.0-1.0>}}
    // ... one entry per category key above
  }},
  "deal_breaker_flags": ["<id>", ...],   // from this fixed set if clearly evidenced:
                                          // open_hipaa_breach, no_fda_clearance, no_soc2, active_litigation
  "uncovered": [
    {{"factor": "<short name>", "evidence": "<why it came up>", "materiality": "high|medium|low"}}
  ]
}}
No prose, no markdown fences — JSON only."""


def build_prompt() -> str:
    cats = "\n".join(f"- {k}" for k in CATEGORY_KEYS)
    return EXTRACT_SYSTEM.format(categories=cats)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return text


def parse_extraction(raw_text: str) -> dict[str, Any]:
    """
    Parse + validate the LLM JSON. Returns:
      {"vendor", "scores": {key: float}, "evidence": {key: str},
       "deal_breaker_flags": set, "uncovered": [...]}
    Missing categories default to neutral 5.0. Robust to stray prose.
    """
    text = _strip_fences(raw_text)
    # tolerate leading/trailing prose by grabbing the outermost JSON object
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    data = json.loads(text)

    raw_scores = data.get("scores", {})
    scores: dict[str, float] = {}
    evidence: dict[str, str] = {}
    for key in CATEGORY_KEYS:
        entry = raw_scores.get(key) or {}
        try:
            s = float(entry.get("score", 5))
        except (TypeError, ValueError):
            s = 5.0
        scores[key] = max(0.0, min(10.0, s))
        evidence[key] = str(entry.get("evidence", ""))

    flags = {f for f in data.get("deal_breaker_flags", []) if isinstance(f, str)}
    uncovered = [u for u in data.get("uncovered", []) if isinstance(u, dict) and u.get("factor")]

    return {
        "vendor": data.get("vendor", "Vendor"),
        "scores": scores,
        "evidence": evidence,
        "deal_breaker_flags": flags,
        "uncovered": uncovered,
    }


async def extract(findings_text: str, llm, *, vendor_hint: str = "") -> dict[str, Any]:
    """
    Run the extractor LLM over the combined findings. `llm` is any object with an
    async `ainvoke([...messages])` returning an object with `.content` (LangChain).
    """
    from langchain_core.messages import SystemMessage, HumanMessage

    human = findings_text
    if vendor_hint:
        human = f"Vendor: {vendor_hint}\n\n{findings_text}"
    resp = await llm.ainvoke([
        SystemMessage(content=build_prompt()),
        HumanMessage(content=human),
    ])
    return parse_extraction(resp.content)
