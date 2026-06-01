"""Shared HTML analysis preparation for Strapi planning commands."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.schema_planner import resolve_planner_context
from src.section_detector import analyze_html_file
from src.section_llm_analyzer import analyze_sections_with_llm


_SECTION_ANALYSIS_CACHE: dict[str, dict[str, Any]] = {}


def prepare_html_analysis_for_planning(
    html_file: str | Path,
    *,
    use_llm_section_analysis: bool = False,
    planner_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build detector output, optionally enriched section-by-section by an LLM."""
    if not use_llm_section_analysis:
        return analyze_html_file(html_file)

    context = resolve_planner_context(planner_context)
    cache_key = section_analysis_cache_key(html_file, context)
    if cache_key in _SECTION_ANALYSIS_CACHE:
        return deepcopy(_SECTION_ANALYSIS_CACHE[cache_key])

    analysis = analyze_html_file(html_file, include_raw_html=True)
    enriched_analysis = analyze_sections_with_llm(analysis, planner_context=context)
    _SECTION_ANALYSIS_CACHE[cache_key] = deepcopy(enriched_analysis)
    return enriched_analysis


def section_analysis_cache_key(html_file: str | Path, context: dict[str, Any]) -> str:
    path = Path(html_file).resolve()
    context_fingerprint = json.dumps(context, sort_keys=True, default=str)
    return f"{path}|{context_fingerprint}"
