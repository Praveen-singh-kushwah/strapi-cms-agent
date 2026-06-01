"""LLM enrichment for deterministic candidate sections.

This module is intentionally separate from the default deterministic detector.
It takes ordered candidate sections, optionally including raw section HTML, and
asks an LLM to enrich one section at a time. The output is merged back into the
deterministic section shape so downstream planners can keep using the same
`html_analysis` contract.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from src.schema_planner import (
    openrouter_headers,
    openrouter_strict_schema,
    resolve_planner_context,
)


SEMANTIC_HINTS = (
    "hero",
    "intro",
    "feature",
    "service",
    "benefit",
    "proof",
    "case_study",
    "comparison",
    "process",
    "timeline",
    "results",
    "calculator",
    "pricing",
    "testimonial",
    "faq",
    "cta",
    "contact",
    "form",
    "table",
    "trust",
    "unknown",
)
DEFAULT_MAX_SECTION_HTML_CHARS = 12000
DEFAULT_MAX_TEXT_PREVIEW_CHARS = 1200


class SectionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    href: str = ""
    type: str = "link"


class SectionMedia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src: str = ""
    alt: str = ""
    type: str = "image"


class SectionTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    caption: str = ""


class SectionFormField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = ""
    name: str = ""
    inputType: str = ""
    required: bool = False


class SectionForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = ""
    method: str = ""
    submitLabel: str = ""
    fields: list[SectionFormField] = Field(default_factory=list)


class SectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    description: str = ""
    text: str = ""
    value: str = ""
    label: str = ""
    period: str = ""
    price: str = ""
    saving: str = ""
    quote: str = ""
    authorName: str = ""
    authorRole: str = ""
    features: list[str] = Field(default_factory=list)
    cta: SectionAction | None = None
    media: SectionMedia | None = None


class EnrichedCandidateSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    semanticHint: str
    sectionType: str = ""
    title: str = ""
    eyebrow: str = ""
    description: str = ""
    body: str = ""
    items: list[SectionItem] = Field(default_factory=list)
    actions: list[SectionAction] = Field(default_factory=list)
    table: SectionTable | None = None
    form: SectionForm | None = None
    media: list[SectionMedia] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


def analyze_sections_with_llm(
    html_analysis: dict[str, Any],
    planner_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enrich all candidate sections in page order using section-level LLM calls.

    If a section-level call fails, that section remains deterministic and gets a
    warning. This keeps the step safe to insert before the CMS planner.
    """
    context = resolve_planner_context(planner_context)
    result = deepcopy(html_analysis)
    sections = result.get("candidateSections", [])
    if not isinstance(sections, list):
        raise ValueError("html_analysis.candidateSections must be a list")

    errors: list[str] = []
    enriched_sections = []
    for index, section in enumerate(sections):
        previous_section = sections[index - 1] if index > 0 else None
        next_section = sections[index + 1] if index + 1 < len(sections) else None
        try:
            enriched = analyze_one_section_with_llm(
                result,
                section,
                previous_section=previous_section,
                next_section=next_section,
                planner_context=context,
            )
            enriched_sections.append(merge_enriched_section(section, enriched))
        except Exception as exc:  # pragma: no cover - network/model dependent
            fallback = deepcopy(section)
            fallback.setdefault("warnings", []).append(f"LLM section analysis failed: {exc}")
            enriched_sections.append(fallback)
            errors.append(f"Section {section.get('index', index + 1)}: {exc}")

    result["candidateSections"] = enriched_sections
    successful_section_count = len(enriched_sections) - len(errors)
    result["sectionAnalysis"] = {
        "usedLLM": True,
        "sectionCount": len(enriched_sections),
        "successfulSectionCount": successful_section_count,
        "errorCount": len(errors),
        "errors": errors,
    }
    return result


def analyze_one_section_with_llm(
    html_analysis: dict[str, Any],
    section: dict[str, Any],
    *,
    previous_section: dict[str, Any] | None = None,
    next_section: dict[str, Any] | None = None,
    planner_context: dict[str, Any] | None = None,
) -> EnrichedCandidateSection:
    """Call the configured LLM provider for one section."""
    context = resolve_planner_context(planner_context)
    if context["provider"] == "openrouter":
        return analyze_one_section_with_openrouter(
            html_analysis,
            section,
            previous_section=previous_section,
            next_section=next_section,
            planner_context=context,
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for LLM section analysis")

    prompt = build_section_analysis_prompt(
        html_analysis,
        section,
        previous_section=previous_section,
        next_section=next_section,
        planner_context=context,
    )
    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=context["modelName"],
        input=[
            {
                "role": "system",
                "content": "You analyze one HTML page section and return only the requested JSON object.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        text_format=EnrichedCandidateSection,
    )

    if response.output_parsed is None:
        raise ValueError("OpenAI section analyzer did not return a parsed section")
    if isinstance(response.output_parsed, EnrichedCandidateSection):
        return response.output_parsed
    return EnrichedCandidateSection.model_validate(response.output_parsed)


def analyze_one_section_with_openrouter(
    html_analysis: dict[str, Any],
    section: dict[str, Any],
    *,
    previous_section: dict[str, Any] | None = None,
    next_section: dict[str, Any] | None = None,
    planner_context: dict[str, Any] | None = None,
) -> EnrichedCandidateSection:
    """Call OpenRouter's OpenAI-compatible API for one section."""
    context = resolve_planner_context(planner_context)
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter section analysis")

    prompt = build_section_analysis_prompt(
        html_analysis,
        section,
        previous_section=previous_section,
        next_section=next_section,
        planner_context=context,
    )
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or "https://openrouter.ai/api/v1",
        default_headers=openrouter_headers(),
    )
    completion = client.chat.completions.create(
        model=context.get("openRouterModelName") or context["modelName"],
        messages=[
            {
                "role": "system",
                "content": "You analyze one HTML page section. Return only valid JSON matching the schema.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format=section_response_format(context),
        max_tokens=int(context["maxTokens"]),
    )

    choices = completion.choices or []
    if not choices or not choices[0].message or not choices[0].message.content:
        raise ValueError("OpenRouter section analyzer returned an empty response")

    content = choices[0].message.content
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {None, "text"}
        )
    return validate_section_analysis_content(str(content))


def build_section_analysis_prompt(
    html_analysis: dict[str, Any],
    section: dict[str, Any],
    *,
    previous_section: dict[str, Any] | None = None,
    next_section: dict[str, Any] | None = None,
    planner_context: dict[str, Any] | None = None,
) -> str:
    """Build the strict prompt for one-section enrichment."""
    context = resolve_planner_context(planner_context)
    max_html_chars = int(context.get("maxSectionHtmlChars") or DEFAULT_MAX_SECTION_HTML_CHARS)
    prompt_payload = {
        "page": html_analysis.get("page", {}),
        "sectionIndex": section.get("index"),
        "previousSection": compact_neighbor_section(previous_section),
        "nextSection": compact_neighbor_section(next_section),
        "deterministicSection": compact_section_for_prompt(section, max_html_chars=max_html_chars),
    }

    return f"""You are analyzing one visual section from a larger HTML page.

Task:
Return one JSON object matching the EnrichedCandidateSection schema.

Rules:
- Analyze only this section. Do not include content from previous or next sections.
- Preserve the exact section index.
- Choose semanticHint from this list when possible: {", ".join(SEMANTIC_HINTS)}.
- Use sectionType for a more specific snake_case meaning, such as roi_timeline, cost_leaks, quick_answer, trust_metrics, guarantee, results_table, or process_steps.
- Extract eyebrow, title, description, body, actions, repeated items, table, form, and media when present.
- Repeated visual cards, steps, phases, metrics, testimonials, FAQ rows, and pricing blocks should be items.
- Preserve user-facing text exactly enough for CMS seeding, but do not invent missing content.
- If unsure, use semanticHint "unknown", set confidence below 0.6, and add a warning.
- Output JSON only.

Input:
{json.dumps(prompt_payload, indent=2, ensure_ascii=False)}
"""


def compact_section_for_prompt(section: dict[str, Any], *, max_html_chars: int) -> dict[str, Any]:
    raw_html = str(section.get("rawHtml") or "")
    compact = {
        "index": section.get("index"),
        "semanticHint": section.get("semanticHint"),
        "tag": section.get("tag"),
        "id": section.get("id"),
        "classes": section.get("classes", []),
        "heading": section.get("heading", ""),
        "headingLevel": section.get("headingLevel", ""),
        "subheadings": section.get("subheadings", []),
        "textPreview": truncate_text(str(section.get("textPreview") or ""), DEFAULT_MAX_TEXT_PREVIEW_CHARS),
        "buttons": section.get("buttons", []),
        "images": section.get("images", []),
        "structuredContent": section.get("structuredContent", {}),
        "structureSignals": section.get("structureSignals", {}),
        "table": section.get("table"),
        "forms": section.get("forms", []),
        "repeatedGroups": compact_repeated_groups(section.get("repeatedGroups", [])),
    }
    if raw_html:
        compact["rawHtml"] = truncate_text(raw_html, max_html_chars)
    return compact


def compact_neighbor_section(section: dict[str, Any] | None) -> dict[str, Any] | None:
    if not section:
        return None
    return {
        "index": section.get("index"),
        "semanticHint": section.get("semanticHint"),
        "heading": section.get("heading", ""),
        "classes": section.get("classes", []),
    }


def compact_repeated_groups(groups: Any) -> list[dict[str, Any]]:
    if not isinstance(groups, list):
        return []
    return [
        {
            "className": group.get("className"),
            "count": group.get("count"),
            "fieldsDetected": group.get("fieldsDetected", []),
            "sampleItems": group.get("sampleItems", []),
        }
        for group in groups
        if isinstance(group, dict)
    ]


def merge_enriched_section(
    deterministic_section: dict[str, Any],
    enriched_section: EnrichedCandidateSection | dict[str, Any],
) -> dict[str, Any]:
    """Merge LLM section analysis back into the deterministic section shape."""
    enriched = (
        enriched_section
        if isinstance(enriched_section, EnrichedCandidateSection)
        else EnrichedCandidateSection.model_validate(enriched_section)
    )
    merged = deepcopy(deterministic_section)
    warnings = list(merged.get("warnings", []))

    if enriched.index != deterministic_section.get("index"):
        warnings.append(
            f"LLM returned section index {enriched.index}; kept deterministic index {deterministic_section.get('index')}"
        )

    semantic_hint = normalize_semantic_hint(enriched.semanticHint)
    if semantic_hint:
        merged["semanticHint"] = semantic_hint
    if enriched.sectionType:
        merged["sectionType"] = snake_case(enriched.sectionType)
    if enriched.confidence is not None:
        merged["llmConfidence"] = enriched.confidence
    if enriched.warnings:
        warnings.extend(enriched.warnings)

    structured_content = dict(merged.get("structuredContent") or {})
    set_if_text(structured_content, "title", enriched.title)
    set_if_text(structured_content, "eyebrow", enriched.eyebrow)
    set_if_text(structured_content, "description", enriched.description)
    set_if_text(structured_content, "body", enriched.body)

    item_values = [item.model_dump(exclude_none=True) for item in enriched.items]
    item_values = [drop_empty_values(item) for item in item_values]
    if item_values:
        structured_content["items"] = item_values

    action_values = [action.model_dump(exclude_none=True) for action in enriched.actions]
    action_values = [drop_empty_values(action) for action in action_values]
    if action_values:
        structured_content["actions"] = action_values
        merged["buttons"] = action_values

    if enriched.table:
        table = enriched.table.model_dump(exclude_none=True)
        merged["table"] = drop_empty_values(table)
        structured_content["table"] = merged["table"]
    if enriched.form:
        form = enriched.form.model_dump(exclude_none=True)
        structured_content["form"] = drop_empty_values(form)
        merged["forms"] = [structured_content["form"]]
    if enriched.media:
        media = [drop_empty_values(item.model_dump(exclude_none=True)) for item in enriched.media]
        structured_content["media"] = media
        merged["images"] = media

    if warnings:
        merged["warnings"] = dedupe_messages(warnings)
    merged["structuredContent"] = structured_content
    return merged


def validate_section_analysis_content(content: str) -> EnrichedCandidateSection:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("LLM section analyzer response must be a JSON object")
    return EnrichedCandidateSection.model_validate(payload)


def section_response_format(context: dict[str, Any]) -> dict[str, Any]:
    mode = str(context.get("structuredOutputMode") or "json_schema").lower()
    if mode in {"json_object", "json", "json_mode"}:
        return {"type": "json_object"}

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "enriched_candidate_section",
            "strict": True,
            "schema": openrouter_strict_schema(EnrichedCandidateSection.model_json_schema()),
        },
    }


def normalize_semantic_hint(value: str) -> str:
    normalized = snake_case(value)
    aliases = {
        "features": "feature",
        "services": "service",
        "testimonials": "testimonial",
        "case": "case_study",
        "case_studies": "case_study",
        "results_table": "results",
        "roi_timeline": "timeline",
        "quick_answer": "intro",
        "trust_metrics": "trust",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in SEMANTIC_HINTS else "unknown"


def set_if_text(target: dict[str, Any], key: str, value: str) -> None:
    if isinstance(value, str) and value.strip():
        target[key] = value.strip()


def drop_empty_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: drop_empty_values(child)
            for key, child in value.items()
            if not is_empty_value(child)
        }
    if isinstance(value, list):
        return [drop_empty_values(item) for item in value if not is_empty_value(item)]
    return value


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n...[truncated]"


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value or "")
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return value.strip("_").lower()


def dedupe_messages(messages: list[str]) -> list[str]:
    seen = set()
    result = []
    for message in messages:
        if message and message not in seen:
            seen.add(message)
            result.append(message)
    return result
