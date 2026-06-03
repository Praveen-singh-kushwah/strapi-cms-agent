"""LLM section planner foundation for Strapi CMS plans.

The deterministic planner in this file mirrors the JSON shape expected from a
future LLM call. It lets the notebook validate the CMS planning contract before
LangGraph/LangChain are introduced.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypedDict

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from src.schema_models import (
    CmsPlan,
    ComponentPlan,
    FieldPlan,
    GlobalBlockPlan,
    GlobalBlocksPlan,
    PageModel,
    SeoPlan,
    SingleTypeAttribute,
)


class AgentState(TypedDict, total=False):
    html_analysis: dict[str, Any]
    cms_plan: dict[str, Any]
    planner_context: dict[str, Any]
    errors: list[str]


DEFAULT_PLANNER_CONTEXT = {
    "cms": "strapi",
    "strapiVersion": "v5",
    "target": "singleType",
    "componentCategoryPrefix": "landing-page",
    "namingStyle": "snake_case_fields",
    "reuseSharedComponents": True,
    "modelName": "gpt-5.4-mini",
    "openRouterModelName": "~openai/gpt-latest",
    "maxTokens": 4096,
    "provider": "openai",
    "structuredOutputMode": "json_schema",
    "compactInput": True,
    "useLLM": "auto",
}

CANONICAL_SECTION_NAMES = ("hero", "features", "testimonials", "pricing", "faq", "contact")
CANONICAL_SECTION_SOURCE_INDEXES = {
    "hero": 1,
    "features": 2,
    "testimonials": 3,
    "pricing": 4,
    "faq": 5,
    "contact": 6,
}
CANONICAL_COMPONENT_ALIASES = {
    "hero": {"hero", "hero-section", "section-hero"},
    "features": {"features", "feature", "features-section", "feature-section", "section-features", "section-feature"},
    "feature-card": {"feature-card", "feature-item", "features-card", "features-item"},
    "testimonials": {
        "testimonials",
        "testimonial",
        "testimonials-section",
        "testimonial-section",
        "section-testimonials",
        "section-testimonial",
    },
    "testimonial-card": {"testimonial-card", "testimonial-item"},
    "pricing": {"pricing", "pricing-section", "section-pricing"},
    "pricing-card": {"pricing-card", "pricing-item", "plan-card", "plan-item"},
    "pricing-feature": {"pricing-feature", "pricing-bullet", "pricing-bullets"},
    "faq": {"faq", "faq-section", "section-faq"},
    "faq-item": {"faq-item", "question-answer", "question-answer-item"},
    "contact": {"contact", "contact-section", "section-contact"},
    "form-config": {"form-config", "contact-form", "form"},
    "form-field": {"form-field", "input-field"},
    "quick-answer": {"quick-answer", "answer-box", "proof-box", "aeo-answer-box"},
    "quick-answer-item": {"quick-answer-item", "answer-item", "proof-item"},
    "timeline": {"timeline", "roi-timeline", "section-timeline"},
    "timeline-item": {"timeline-item", "timeline-step", "timeline-phase", "roi-phase"},
    "process": {"process", "process-section", "steps", "process-steps"},
    "process-step": {"process-step", "step-item", "process-item"},
    "results-table": {"results-table", "proof-table", "savings-table", "results"},
    "calculator": {"calculator", "calculator-section", "finops-calculator"},
    "stats-band": {"stats-band", "trust-band", "metrics-band", "stats"},
    "stat-item": {"stat-item", "metric-item", "trust-item"},
    "guarantee": {"guarantee", "guarantee-box", "promise"},
    "cta": {"cta", "final-cta", "call-to-action"},
}
CANONICAL_COMPONENT_BY_HINT = {
    "hero": "hero",
    "feature": "features",
    "testimonial": "testimonials",
    "pricing": "pricing",
    "faq": "faq",
    "contact": "contact",
    "form": "contact",
    "timeline": "timeline",
    "process": "process",
    "results": "results-table",
    "calculator": "calculator",
    "trust": "stats-band",
    "cta": "cta",
}
CANONICAL_COMPONENT_BY_SECTION_TYPE = {
    "roi_timeline": "timeline",
    "timeline": "timeline",
    "process_steps": "process",
    "finops_process": "process",
    "results_table": "results-table",
    "proof_table": "results-table",
    "savings_table": "results-table",
    "quick_answer": "quick-answer",
    "answer_box": "quick-answer",
    "proof_box": "quick-answer",
    "aeo_answer_box": "quick-answer",
    "cost_leaks": "features",
    "finops_calculator": "calculator",
    "cost_calculator": "calculator",
    "cost_savings_calculator": "calculator",
    "trust_metrics": "stats-band",
    "trust_band": "stats-band",
    "stats_band": "stats-band",
    "metrics_band": "stats-band",
    "guarantee": "guarantee",
    "guarantee_box": "guarantee",
    "final_cta": "cta",
    "call_to_action": "cta",
}
SEMANTIC_COMPONENT_TYPE_FRAGMENTS = (
    ("quick_answer", "quick-answer"),
    ("answer_box", "quick-answer"),
    ("proof_box", "quick-answer"),
    ("timeline", "timeline"),
    ("process", "process"),
    ("step", "process"),
    ("result", "results-table"),
    ("table", "results-table"),
    ("proof", "results-table"),
    ("calculator", "calculator"),
    ("calc", "calculator"),
    ("trust", "stats-band"),
    ("stat", "stats-band"),
    ("metric", "stats-band"),
    ("guarantee", "guarantee"),
    ("cta", "cta"),
    ("call_to_action", "cta"),
)
STABLE_ATTRIBUTE_HINTS = {"hero", "feature", "testimonial", "pricing", "faq", "contact"}
LAYOUT_SECTION_HINTS = {"header", "footer"}
GENERIC_SECTION_COMPONENT = "content-section"
GENERIC_ITEM_COMPONENT = "content-item"
MAX_API_NAME_LENGTH = 54
MAX_ATTRIBUTE_NAME_LENGTH = 56


def llm_section_planner_node(state: AgentState) -> AgentState:
    """LangGraph-compatible node shape for section planning.

    Uses the real OpenAI planner when configured, and falls back to the
    deterministic planner when no API key is present or LLM mode is disabled.
    """
    try:
        html_analysis = state["html_analysis"]
        context = resolve_planner_context(state.get("planner_context", {}))
        cms_plan = generate_llm_cms_plan(html_analysis, context) if should_use_llm(context) else generate_cms_plan(
            html_analysis,
            context,
        )
        return {**state, "cms_plan": cms_plan.model_dump()}
    except Exception as exc:  # pragma: no cover - notebook-friendly error capture
        errors = [*state.get("errors", []), str(exc)]
        return {**state, "errors": errors}


def build_section_planner_prompt(
    html_analysis: dict[str, Any],
    planner_context: dict[str, Any] | None = None,
) -> str:
    """Build the strict prompt that the future LLM planner should receive."""
    context = resolve_planner_context(planner_context)
    prompt_analysis = compact_html_analysis(html_analysis) if context.get("compactInput") else html_analysis
    public_context = public_planner_context(context)
    return f"""You are a Strapi CMS architect.

You will receive structured HTML section analysis from a deterministic parser.

Your task:
Convert it into a Strapi CMS plan.

Rules:
- Output only valid JSON matching the CmsPlan schema.
- The root object must contain exactly: pageModel, seo, globalBlocks, components, singleTypeAttributes, seedData, warnings.
- Do not generate code files.
- Use a singleType for the page.
- Add an SEO component.
- Each visual page section should become one non-repeatable section component.
- Repeated cards/items inside a section should become repeatable nested components.
- Use snake_case field names.
- Use Strapi-safe component names in kebab-case.
- Use media fields for images.
- Use text fields for long descriptions.
- Use string fields for titles, labels, URLs, and prices.
- Use boolean fields for flags such as isHighlighted.
- Preserve section order.
- Do not hallucinate content not present in the input.
- Planner context is configuration only. Never use model/provider names as CMS page names or content.
- Derive pageModel only from the HTML page title and section content.
- Only create singleTypeAttributes and seedData entries for sections present in candidateSections.
- If candidateSections contains a subset of the page, do not infer missing page sections from the title or global blocks.
- seedData keys must exactly match singleTypeAttributes names. Use null for optional seed sections that are not attributes.
- Include warnings when uncertain.

Planner context:
{json.dumps(public_context, indent=2)}

HTML analysis:
{json.dumps(prompt_analysis, indent=2)}
"""


def public_planner_context(context: dict[str, Any]) -> dict[str, Any]:
    """Expose only CMS planning settings to the LLM.

    Runtime details such as the LLM model name are useful to Python, but they can
    confuse the planner into treating the model name as page content.
    """
    allowed_keys = (
        "cms",
        "strapiVersion",
        "target",
        "componentCategoryPrefix",
        "namingStyle",
        "reuseSharedComponents",
    )
    return {key: context[key] for key in allowed_keys if key in context}


def compact_html_analysis(html_analysis: dict[str, Any]) -> dict[str, Any]:
    """Reduce detector output before sending it to an LLM.

    The full detector output is useful for debugging, but the LLM planner only
    needs page/global summaries, semantic hints, structural signals, and
    structured content. This keeps OpenRouter prompts under smaller limits.
    """
    return {
        "page": html_analysis.get("page", {}),
        "globalBlocks": compact_global_blocks(html_analysis.get("globalBlocks", {})),
        "candidateSections": [
            compact_candidate_section(section)
            for section in html_analysis.get("candidateSections", [])
        ],
    }


def compact_global_blocks(global_blocks: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in ("header", "footer"):
        block = global_blocks.get(key)
        if not block:
            result[key] = None
            continue
        result[key] = {
            "brand": block.get("brand", ""),
            "navigationLinks": block.get("navigationLinks") or block.get("links") or [],
            "cta": block.get("cta"),
            "description": block.get("description", ""),
            "copyright": block.get("copyright", ""),
        }
    return result


def compact_candidate_section(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": section.get("index"),
        "semanticHint": section.get("semanticHint"),
        "id": section.get("id"),
        "heading": section.get("heading"),
        "headingLevel": section.get("headingLevel"),
        "structuredContent": section.get("structuredContent", {}),
        "structureSignals": section.get("structureSignals", {}),
        "repeatedGroups": [
            {
                "className": group.get("className"),
                "count": group.get("count"),
                "fieldsDetected": group.get("fieldsDetected", []),
                "sampleItems": group.get("sampleItems", []),
            }
            for group in section.get("repeatedGroups", [])
        ],
    }


def generate_llm_cms_plan(
    html_analysis: dict[str, Any],
    planner_context: dict[str, Any] | None = None,
) -> CmsPlan:
    """Generate a validated CMS plan with OpenAI Structured Outputs."""
    context = resolve_planner_context(planner_context)
    if context["provider"] == "openrouter":
        return generate_openrouter_cms_plan(html_analysis, context)

    model_name = context["modelName"]
    prompt = build_section_planner_prompt(html_analysis, context)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required to run the real LLM planner")

    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=model_name,
        input=[
            {
                "role": "system",
                "content": "You are a precise Strapi CMS architect. Return only the structured CMS plan.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        text_format=CmsPlan,
    )

    if response.output_parsed is None:
        raise ValueError("OpenAI planner did not return a parsed CmsPlan")

    return response.output_parsed if isinstance(response.output_parsed, CmsPlan) else CmsPlan.model_validate(
        response.output_parsed,
    )


def generate_openrouter_cms_plan(
    html_analysis: dict[str, Any],
    planner_context: dict[str, Any] | None = None,
) -> CmsPlan:
    """Generate a validated CMS plan through OpenRouter's OpenAI-compatible API."""
    context = resolve_planner_context(planner_context)
    model_name = context.get("openRouterModelName") or context["modelName"]
    prompt = build_section_planner_prompt(html_analysis, context)
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required to run the OpenRouter planner")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or "https://openrouter.ai/api/v1",
        default_headers=openrouter_headers(),
    )
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are a precise Strapi CMS architect. Return only valid JSON matching the requested schema.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format=openrouter_response_format(context),
        max_tokens=int(context["maxTokens"]),
    )

    choices = completion.choices or []
    if not choices:
        raise ValueError(
            "OpenRouter planner returned no choices. "
            f"Raw response: {completion.model_dump(exclude_none=True)}"
        )

    choice = choices[0]
    content = choice.message.content if choice.message else None
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {None, "text"}
        )
    if not content:
        raise ValueError(
            "OpenRouter planner returned an empty response "
            f"(finish_reason={choice.finish_reason}, message={choice.message.model_dump()})"
        )

    return validate_llm_plan_content(content)


def validate_llm_plan_content(content: str) -> CmsPlan:
    """Validate LLM JSON and repair small shape issues when safe.

    The LLM can occasionally include seed entries for sections it inferred but
    did not actually add as single type attributes. Those keys cannot be used by
    the Strapi generator, so we drop them and preserve the issue as a warning.
    It can also emit SEO seed data while forgetting the matching SEO attribute;
    in that case, adding the missing attribute is deterministic and safe.
    """
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("LLM planner response must be a JSON object")

    repair_page_identity(payload)
    repair_component_file_names(payload)
    repair_component_uids(payload)
    repair_section_attribute_names(payload)
    repair_dynamic_sections_attribute(payload)
    repair_generic_component_references(payload)
    repair_canonical_contract(payload)
    add_missing_seo_attribute(payload)

    try:
        return CmsPlan.model_validate(payload)
    except ValidationError as exc:
        if "seedData has keys not present in attributes" not in str(exc):
            raise

        attribute_names = single_type_attribute_names(payload)
        seed_data = payload.get("seedData", {})
        if not isinstance(seed_data, dict):
            raise

        removed_keys = sorted(set(seed_data) - attribute_names)
        if not removed_keys:
            raise

        payload["seedData"] = {
            key: value
            for key, value in seed_data.items()
            if key in attribute_names
        }
        append_warning(
            payload,
            "Removed seedData keys that were not present in singleTypeAttributes: "
            + ", ".join(removed_keys),
        )
        return CmsPlan.model_validate(payload)


def repair_page_identity(payload: dict[str, Any]) -> None:
    page_model = payload.get("pageModel", {})
    if not isinstance(page_model, dict):
        return

    suspicious_names = llm_model_identity_names()
    page_values = {
        str(page_model.get("apiName", "")).lower(),
        str(page_model.get("displayName", "")).lower(),
        str(page_model.get("singularName", "")).lower(),
        str(page_model.get("pluralName", "")).lower(),
    }
    if not suspicious_names.intersection(page_values):
        return

    page_model.update(
        {
            "kind": "singleType",
            "apiName": "landing-page",
            "displayName": "Landing Page",
            "singularName": "landing-page",
            "pluralName": "landing-pages",
            "description": "CMS single type for the landing page.",
        }
    )
    append_warning(payload, "Repaired pageModel because it used the LLM model name as the page identity.")


def repair_component_uids(payload: dict[str, Any]) -> None:
    components = payload.get("components", [])
    if not isinstance(components, list):
        return

    replacements = {}
    for component in components:
        if not isinstance(component, dict):
            continue
        uid = component.get("uid")
        category = component.get("category")
        file_name = component.get("fileName")
        if not all(isinstance(value, str) for value in (uid, category, file_name)):
            continue
        if "." in uid:
            continue

        expected_prefix = f"{category}-"
        if uid.startswith(expected_prefix):
            replacements[uid] = f"{category}.{uid.removeprefix(expected_prefix)}"
        else:
            replacements[uid] = f"{category}.{file_name}"

    if not replacements:
        return

    for component in components:
        if not isinstance(component, dict):
            continue
        if component.get("uid") in replacements:
            component["uid"] = replacements[component["uid"]]
        repair_component_references(component.get("fields", []), replacements)

    repair_component_references(payload.get("singleTypeAttributes", []), replacements)
    append_warning(
        payload,
        "Repaired component UIDs to category.component-name format: "
        + ", ".join(f"{old} -> {new}" for old, new in sorted(replacements.items())),
    )


def repair_component_file_names(payload: dict[str, Any]) -> None:
    components = payload.get("components")
    if not isinstance(components, list):
        return

    replacements = {}
    for component in components:
        if not isinstance(component, dict):
            continue

        file_name = component.get("fileName")
        if not isinstance(file_name, str) or not file_name:
            continue

        normalized = slugify(file_name.removesuffix(".json"))
        if normalized and normalized != file_name:
            component["fileName"] = normalized
            replacements[file_name] = normalized

    if replacements:
        append_warning(
            payload,
            "Repaired component fileName values to kebab-case names without extensions: "
            + ", ".join(f"{old} -> {new}" for old, new in sorted(replacements.items())),
        )


def repair_component_references(items: Any, replacements: dict[str, str]) -> None:
    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        component = item.get("component")
        if component in replacements:
            item["component"] = replacements[component]


def repair_generic_component_references(payload: dict[str, Any]) -> None:
    components = payload.get("components")
    if not isinstance(components, list):
        return

    replacements = []
    for component in components:
        if not isinstance(component, dict):
            continue
        parent_uid = component.get("uid") if isinstance(component.get("uid"), str) else ""
        fields = component.get("fields")
        if not isinstance(fields, list):
            continue
        for field in fields:
            repaired = repair_component_reference_item(field, parent_uid, components)
            if repaired:
                replacements.append(repaired)

    attributes = payload.get("singleTypeAttributes")
    if isinstance(attributes, list):
        for attribute in attributes:
            repaired = repair_component_reference_item(attribute, "", components)
            if repaired:
                replacements.append(repaired)

    if replacements:
        append_warning(
            payload,
            "Repaired generic component references: "
            + ", ".join(f"{name} -> {component}" for name, component in replacements),
        )


def repair_component_reference_item(
    item: Any,
    parent_uid: str,
    components: list[Any],
) -> tuple[str, str] | None:
    if not isinstance(item, dict) or item.get("type") != "component":
        return None

    name = item.get("name")
    if not isinstance(name, str) or not name:
        return None

    current = item.get("component")
    if isinstance(current, str) and current in available_component_uids(components):
        return None

    if current not in (None, "", "component", "components", "item", "items", "section"):
        return None

    inferred = infer_component_reference(name, parent_uid, components)
    if not inferred:
        return None

    item["component"] = inferred
    return name, inferred


def infer_component_reference(name: str, parent_uid: str, components: list[Any]) -> str | None:
    normalized_name = name.lower()
    normalized_parent = parent_uid.lower()

    if normalized_name in {"seo"}:
        return "shared.seo"
    if "cta" in normalized_name or "link" in normalized_name or "button" in normalized_name:
        return "shared.link"
    if "faq" in normalized_name:
        return find_component_uid_by_aliases(components, {"faq-item", "item-faq"})
    if "testimonial" in normalized_name:
        return find_component_uid_by_aliases(components, {"testimonial-card", "testimonial-item"})
    if "pricing" in normalized_name:
        return find_component_uid_by_aliases(components, {"pricing-card", "pricing-item"})
    if "feature" in normalized_name:
        return find_component_uid_by_aliases(components, {"feature-card", "feature-item"})
    if "form" in normalized_name and "field" in normalized_name:
        return find_component_uid_by_aliases(components, {"form-field"})
    if normalized_name == "form":
        return find_component_uid_by_aliases(components, {"form-config", "contact-form"})
    if normalized_name in {"fields"} and "form" in normalized_parent:
        return find_component_uid_by_aliases(components, {"form-field"})
    if normalized_name in {"features", "bullet_points", "bullets"} and "pricing" in normalized_parent:
        return find_component_uid_by_aliases(components, {"pricing-feature", "text-item"}) or "shared.text-item"
    if normalized_name in {"items", "cards"}:
        if "feature" in normalized_parent:
            return find_component_uid_by_aliases(components, {"feature-card", "feature-item"})
        if "testimonial" in normalized_parent:
            return find_component_uid_by_aliases(components, {"testimonial-card", "testimonial-item"})
        if "pricing" in normalized_parent:
            return find_component_uid_by_aliases(components, {"pricing-card", "pricing-item"})
        if "faq" in normalized_parent:
            return find_component_uid_by_aliases(components, {"faq-item"})

    return find_section_component_uid(components, normalized_name)


def available_component_uids(components: list[Any]) -> set[str]:
    return {
        component.get("uid")
        for component in components
        if isinstance(component, dict) and isinstance(component.get("uid"), str)
    } | {"shared.link", "shared.seo", "shared.text-item"}


def find_component_uid_by_aliases(components: list[Any], aliases: set[str]) -> str | None:
    for component in components:
        if not isinstance(component, dict):
            continue
        uid = component.get("uid")
        if not isinstance(uid, str) or not uid:
            continue
        file_name = component.get("fileName")
        display_name = component.get("displayName")
        candidates = {
            uid.rsplit(".", 1)[-1],
            str(file_name or ""),
            slugify(str(display_name or "")),
        }
        if candidates.intersection(aliases):
            return uid
    return None


def repair_canonical_contract(payload: dict[str, Any]) -> None:
    """Normalize common LLM variants into the MVP CMS plan contract."""
    components = payload.get("components")
    if not isinstance(components, list):
        normalize_seed_data_shape(payload)
        return

    replacements = canonicalize_component_names(payload)
    if replacements:
        for component in components:
            if isinstance(component, dict):
                repair_component_references(component.get("fields", []), replacements)
        repair_component_references(payload.get("singleTypeAttributes", []), replacements)
        append_warning(
            payload,
            "Normalized component names to canonical CMS contract: "
            + ", ".join(f"{old} -> {new}" for old, new in sorted(replacements.items())),
        )

    ensure_canonical_nested_components(payload)
    canonicalize_component_fields(payload)
    dedupe_components_by_uid(payload)
    normalize_seed_data_shape(payload)


def canonicalize_component_names(payload: dict[str, Any]) -> dict[str, str]:
    components = payload.get("components")
    if not isinstance(components, list):
        return {}

    replacements = {}
    for component in components:
        if not isinstance(component, dict):
            continue

        canonical_name = canonical_component_name(component)
        if not canonical_name:
            continue

        category = component.get("category")
        if not isinstance(category, str) or not category:
            category = "landing-page"
            component["category"] = category

        old_uid = component.get("uid")
        new_uid = f"{category}.{canonical_name}"
        component["uid"] = new_uid
        component["fileName"] = canonical_name
        component["displayName"] = canonical_display_name(canonical_name)

        if isinstance(old_uid, str) and old_uid != new_uid:
            replacements[old_uid] = new_uid

    return replacements


def canonical_component_name(component: dict[str, Any]) -> str | None:
    candidates = {
        slugify(str(component.get("fileName") or "")),
        slugify(str(component.get("displayName") or "")),
    }
    uid = component.get("uid")
    if isinstance(uid, str) and uid:
        candidates.add(slugify(uid.rsplit(".", 1)[-1]))

    for canonical_name, aliases in CANONICAL_COMPONENT_ALIASES.items():
        if candidates.intersection(aliases):
            return canonical_name

    return None


def canonical_display_name(file_name: str) -> str:
    display_names = {
        "faq": "FAQ",
        "faq-item": "FAQ Item",
    }
    return display_names.get(file_name, " ".join(part.capitalize() for part in file_name.split("-")))


def ensure_canonical_nested_components(payload: dict[str, Any]) -> None:
    components = payload.get("components")
    if not isinstance(components, list):
        return

    category = landing_page_component_category(components)
    required = set()
    existing = {
        component.get("uid")
        for component in components
        if isinstance(component, dict) and isinstance(component.get("uid"), str)
    }

    for component in components:
        if not isinstance(component, dict):
            continue
        suffix = component_suffix(component)
        if suffix == "features":
            required.add("feature-card")
        elif suffix == "testimonials":
            required.add("testimonial-card")
        elif suffix == "pricing":
            required.update({"pricing-card", "pricing-feature"})
        elif suffix == "pricing-card":
            required.add("pricing-feature")
        elif suffix == "faq":
            required.add("faq-item")
        elif suffix == "contact":
            required.update({"form-config", "form-field"})
        elif suffix == "form-config":
            required.add("form-field")

    added = []
    for file_name in sorted(required):
        uid = f"{category}.{file_name}"
        if uid in existing:
            continue
        components.append(
            {
                "uid": uid,
                "category": category,
                "displayName": canonical_display_name(file_name),
                "fileName": file_name,
                "fields": canonical_component_fields(file_name, category),
            }
        )
        existing.add(uid)
        added.append(uid)

    if added:
        append_warning(
            payload,
            "Added missing nested components required by the canonical CMS contract: "
            + ", ".join(added),
        )


def canonicalize_component_fields(payload: dict[str, Any]) -> None:
    components = payload.get("components")
    if not isinstance(components, list):
        return

    changed = []
    for component in components:
        if not isinstance(component, dict):
            continue
        file_name = component_suffix(component)
        fields = canonical_component_fields(file_name, component.get("category") or "landing-page")
        if not fields:
            continue
        if component.get("fields") != fields:
            component["fields"] = fields
            changed.append(component.get("uid", file_name))

    if changed:
        append_warning(
            payload,
            "Normalized component fields to the canonical CMS contract: "
            + ", ".join(str(value) for value in changed),
        )


def canonical_component_fields(file_name: str, category: str) -> list[dict[str, Any]]:
    if file_name == "hero":
        return [
            field_plan("eyebrow", "string"),
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
            field_plan("primary_cta", "component", component="shared.link", repeatable=False),
            field_plan("secondary_cta", "component", component="shared.link", repeatable=False),
            field_plan("image", "media", multiple=False, allowedTypes=["images"]),
        ]
    if file_name == "features":
        return [
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
            field_plan("items", "component", component=f"{category}.feature-card", repeatable=True),
        ]
    if file_name == "feature-card":
        return [
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
        ]
    if file_name == "testimonials":
        return [
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
            field_plan("items", "component", component=f"{category}.testimonial-card", repeatable=True),
        ]
    if file_name == "testimonial-card":
        return [
            field_plan("quote", "text", required=True),
            field_plan("author_name", "string"),
            field_plan("author_role", "string"),
        ]
    if file_name == "pricing":
        return [
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
            field_plan("items", "component", component=f"{category}.pricing-card", repeatable=True),
        ]
    if file_name == "pricing-card":
        return [
            field_plan("title", "string", required=True),
            field_plan("price", "string"),
            field_plan("description", "text"),
            field_plan("features", "component", component=f"{category}.pricing-feature", repeatable=True),
            field_plan("is_highlighted", "boolean"),
        ]
    if file_name == "pricing-feature":
        return [
            field_plan("text", "string", required=True),
        ]
    if file_name == "faq":
        return [
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
            field_plan("items", "component", component=f"{category}.faq-item", repeatable=True),
        ]
    if file_name == "faq-item":
        return [
            field_plan("question", "string", required=True),
            field_plan("answer", "text", required=True),
        ]
    if file_name == "contact":
        return [
            field_plan("title", "string", required=True),
            field_plan("description", "text"),
            field_plan("form", "component", component=f"{category}.form-config", repeatable=False),
        ]
    if file_name == "form-config":
        return [
            field_plan("action", "string"),
            field_plan("method", "string"),
            field_plan("submit_label", "string"),
            field_plan("fields", "component", component=f"{category}.form-field", repeatable=True),
        ]
    if file_name == "form-field":
        return [
            field_plan("label", "string"),
            field_plan("name", "string", required=True),
            field_plan("input_type", "string"),
            field_plan("required", "boolean"),
        ]
    return []


def field_plan(
    name: str,
    field_type: str,
    required: bool = False,
    component: str | None = None,
    repeatable: bool | None = None,
    multiple: bool | None = None,
    allowedTypes: list[str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "type": field_type,
        "required": required,
    }
    if component is not None:
        result["component"] = component
    if repeatable is not None:
        result["repeatable"] = repeatable
    if multiple is not None:
        result["multiple"] = multiple
    if allowedTypes is not None:
        result["allowedTypes"] = allowedTypes
    return result


def landing_page_component_category(components: list[Any]) -> str:
    for component in components:
        if not isinstance(component, dict):
            continue
        category = component.get("category")
        if isinstance(category, str) and category and category != "shared":
            return category
    return "landing-page"


def component_suffix(component: dict[str, Any]) -> str:
    uid = component.get("uid")
    if isinstance(uid, str) and "." in uid:
        return uid.rsplit(".", 1)[-1]
    return slugify(str(component.get("fileName") or ""))


def dedupe_components_by_uid(payload: dict[str, Any]) -> None:
    components = payload.get("components")
    if not isinstance(components, list):
        return

    result = []
    seen = set()
    removed = []
    for component in components:
        if not isinstance(component, dict):
            continue
        uid = component.get("uid")
        if not isinstance(uid, str) or uid not in seen:
            result.append(component)
            if isinstance(uid, str):
                seen.add(uid)
            continue
        removed.append(uid)

    if removed:
        payload["components"] = result
        append_warning(payload, "Removed duplicate components after canonical normalization: " + ", ".join(removed))


def normalize_seed_data_shape(payload: dict[str, Any]) -> None:
    seed_data = payload.get("seedData")
    if not isinstance(seed_data, dict):
        return

    normalize_hero_seed(seed_data.get("hero"))
    normalize_feature_seed(seed_data.get("features"))
    normalize_items_seed(seed_data.get("testimonials"), ("testimonial_cards", "testimonial_items", "testimonials"))
    normalize_items_seed(seed_data.get("pricing"), ("pricing_cards", "pricing_items", "plans", "cards"))
    normalize_items_seed(seed_data.get("faq"), ("faq_items", "questions"))
    normalize_pricing_seed(seed_data.get("pricing"))
    normalize_contact_seed(seed_data.get("contact"))


def normalize_hero_seed(seed: Any) -> None:
    if not isinstance(seed, dict):
        return

    for prefix in ("primary_cta", "secondary_cta"):
        if isinstance(seed.get(prefix), dict):
            normalize_link_seed(seed[prefix])
            continue

        label = seed.pop(f"{prefix}_label", None)
        url = seed.pop(f"{prefix}_url", None)
        href = seed.pop(f"{prefix}_href", None)
        if label is None and url is None and href is None:
            continue
        seed[prefix] = {
            "text": label or "",
            "url": url or href or "",
        }


def normalize_items_seed(seed: Any, aliases: tuple[str, ...]) -> None:
    if not isinstance(seed, dict):
        return

    if "items" not in seed:
        for alias in aliases:
            if alias in seed:
                seed["items"] = seed.pop(alias)
                break

    items = seed.get("items")
    if not isinstance(items, list):
        return

    for item in items:
        if isinstance(item, dict):
            normalize_link_seed(item.get("cta"))


def normalize_feature_seed(seed: Any) -> None:
    normalize_items_seed(seed, ("feature_cards", "feature_items", "cards"))
    if not isinstance(seed, dict):
        return

    items = seed.get("items")
    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        item.pop("image", None)
        item.pop("cta", None)


def normalize_pricing_seed(seed: Any) -> None:
    if not isinstance(seed, dict):
        return

    normalize_items_seed(seed, ("pricing_cards", "pricing_items", "plans", "cards"))
    items = seed.get("items")
    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        features = item.get("features")
        if not isinstance(features, list):
            continue
        item["features"] = [normalize_pricing_feature_seed(feature) for feature in features]


def normalize_pricing_feature_seed(feature: Any) -> dict[str, str]:
    if isinstance(feature, dict):
        text = feature.get("text", feature.get("value", feature.get("label", "")))
        return {"text": str(text or "")}
    return {"text": str(feature or "")}


def normalize_contact_seed(seed: Any) -> None:
    if not isinstance(seed, dict):
        return

    form = seed.get("form")
    if not isinstance(form, dict):
        form = {}
        seed["form"] = form

    form_action = seed.pop("form_action", None)
    form_method = seed.pop("form_method", None)
    submit_label = seed.pop("submit_label", None)
    form_fields = seed.pop("form_fields", None)

    if form_action is not None and "action" not in form:
        form["action"] = form_action
    if form_method is not None and "method" not in form:
        form["method"] = form_method
    if submit_label is not None and "submit_label" not in form:
        form["submit_label"] = submit_label
    if form_fields is not None and "fields" not in form:
        form["fields"] = form_fields

    fields = form.get("fields")
    if not isinstance(fields, list):
        return
    for field in fields:
        if not isinstance(field, dict):
            continue
        if "input_type" not in field and "type" in field:
            field["input_type"] = field.pop("type")


def normalize_link_seed(seed: Any) -> None:
    if not isinstance(seed, dict):
        return
    if "url" not in seed and "href" in seed:
        seed["url"] = seed.pop("href")


def repair_section_attribute_names(payload: dict[str, Any]) -> None:
    attributes = payload.get("singleTypeAttributes", [])
    seed_data = payload.get("seedData", {})
    if not isinstance(attributes, list) or not isinstance(seed_data, dict):
        return

    canonical_names = set(CANONICAL_SECTION_NAMES)
    existing_names = {
        attribute.get("name")
        for attribute in attributes
        if isinstance(attribute, dict) and isinstance(attribute.get("name"), str)
    }
    replacements = {}

    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        name = attribute.get("name")
        if not isinstance(name, str) or not name.endswith("_section"):
            continue

        candidate = name.removesuffix("_section")
        if candidate not in canonical_names:
            continue
        if candidate in existing_names:
            continue

        attribute["name"] = candidate
        replacements[name] = candidate
        existing_names.discard(name)
        existing_names.add(candidate)

    if not replacements:
        return

    for old_name, new_name in replacements.items():
        if old_name in seed_data and new_name not in seed_data:
            seed_data[new_name] = seed_data.pop(old_name)

    append_warning(
        payload,
        "Repaired section attribute names to match canonical seedData keys: "
        + ", ".join(f"{old} -> {new}" for old, new in sorted(replacements.items())),
    )


def repair_dynamic_sections_attribute(payload: dict[str, Any]) -> None:
    """Convert generic title/description/sections page models to canonical fields.

    Some LLMs prefer a dynamic-zone-like `sections` attribute. For this MVP our
    seed data and generator contract are keyed by semantic section names, so we
    normalize that shape before seed keys are compared with attributes.
    """
    attributes = payload.get("singleTypeAttributes")
    seed_data = payload.get("seedData")
    components = payload.get("components")
    if not isinstance(attributes, list) or not isinstance(seed_data, dict) or not isinstance(components, list):
        return

    attribute_names = {
        attribute.get("name")
        for attribute in attributes
        if isinstance(attribute, dict) and isinstance(attribute.get("name"), str)
    }
    section_seed_names = [name for name in CANONICAL_SECTION_NAMES if seed_data.get(name) is not None]
    if "sections" not in attribute_names or not section_seed_names:
        return

    kept_attributes = [
        attribute
        for attribute in attributes
        if isinstance(attribute, dict)
        and attribute.get("name") not in {"title", "description", "sections"}
        and attribute.get("name") not in section_seed_names
    ]

    added_attributes = []
    for section_name in section_seed_names:
        component_uid = find_section_component_uid(components, section_name)
        if not component_uid:
            continue
        added_attributes.append(
            {
                "name": section_name,
                "type": "component",
                "component": component_uid,
                "repeatable": False,
                "sourceSectionIndex": section_source_index(section_name),
            }
        )

    if not added_attributes:
        return

    payload["singleTypeAttributes"] = kept_attributes + added_attributes
    append_warning(
        payload,
        "Repaired generic sections attribute into canonical section attributes: "
        + ", ".join(attribute["name"] for attribute in added_attributes),
    )


def find_section_component_uid(components: list[Any], section_name: str) -> str | None:
    aliases = section_component_aliases(section_name)

    for component in components:
        if not isinstance(component, dict):
            continue
        uid = component.get("uid")
        if not isinstance(uid, str) or not uid:
            continue
        file_name = component.get("fileName")
        display_name = component.get("displayName")
        candidates = [
            uid.rsplit(".", 1)[-1],
            str(file_name or ""),
            slugify(str(display_name or "")),
        ]
        if any(candidate in aliases for candidate in candidates):
            return uid

    return None


def section_component_aliases(section_name: str) -> set[str]:
    singular = {
        "features": "feature",
        "testimonials": "testimonial",
    }.get(section_name, section_name)

    return {
        section_name,
        singular,
        f"{section_name}-section",
        f"{singular}-section",
        f"section-{section_name}",
        f"section-{singular}",
    }


def section_source_index(section_name: str) -> int | None:
    return CANONICAL_SECTION_SOURCE_INDEXES.get(section_name)


def llm_model_identity_names() -> set[str]:
    names = set()
    for value in (
        os.getenv("MODEL_NAME", ""),
        os.getenv("OPENROUTER_MODEL_NAME", ""),
        DEFAULT_PLANNER_CONTEXT["modelName"],
        DEFAULT_PLANNER_CONTEXT["openRouterModelName"],
    ):
        if not value:
            continue
        raw = value.rsplit("/", 1)[-1].replace("~", "")
        names.add(raw.lower())
        names.add(slugify(raw))
        names.add(raw.replace("-", " ").replace("_", " ").title().lower())
    return names


def add_missing_seo_attribute(payload: dict[str, Any]) -> None:
    seed_data = payload.get("seedData", {})
    if not isinstance(seed_data, dict) or "seo" not in seed_data:
        return

    if "seo" in single_type_attribute_names(payload):
        return

    attributes = payload.setdefault("singleTypeAttributes", [])
    if not isinstance(attributes, list):
        return

    attributes.insert(
        0,
        {
            "name": "seo",
            "type": "component",
            "component": "shared.seo",
            "repeatable": False,
            "sourceSectionIndex": None,
        },
    )
    append_warning(payload, "Added missing seo singleTypeAttribute for seedData.seo.")


def single_type_attribute_names(payload: dict[str, Any]) -> set[str]:
    attributes = payload.get("singleTypeAttributes") or []
    if not isinstance(attributes, list):
        return set()

    return {
        attribute.get("name")
        for attribute in attributes
        if isinstance(attribute, dict) and isinstance(attribute.get("name"), str)
    }


def append_warning(payload: dict[str, Any], message: str) -> None:
    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        payload["warnings"] = warnings
    warnings.append(message)


def openrouter_response_format(context: dict[str, Any]) -> dict[str, Any]:
    mode = str(context.get("structuredOutputMode") or "json_schema").lower()
    if mode in {"json_object", "json", "json_mode"}:
        return {"type": "json_object"}

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cms_plan",
            "strict": True,
            "schema": openrouter_strict_schema(CmsPlan.model_json_schema()),
        },
    }


def openrouter_headers() -> dict[str, str]:
    headers = {}
    if os.getenv("OPENROUTER_SITE_URL"):
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "")
    if os.getenv("OPENROUTER_SITE_NAME"):
        headers["X-OpenRouter-Title"] = os.getenv("OPENROUTER_SITE_NAME", "")
    return headers


def openrouter_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adjust Pydantic JSON Schema for providers that require strict objects.

    Some OpenRouter providers reject object schemas unless every property is
    listed in `required`. This adapter changes only the schema sent to the LLM;
    the returned data is still validated by CmsPlan afterward.
    """
    normalized = json.loads(json.dumps(schema))
    force_required_properties(normalized)
    return normalized


def force_required_properties(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" and isinstance(node.get("properties"), dict):
            node["required"] = list(node["properties"].keys())
            node["additionalProperties"] = False

        for value in node.values():
            force_required_properties(value)
    elif isinstance(node, list):
        for item in node:
            force_required_properties(item)


def should_use_llm(planner_context: dict[str, Any] | None = None) -> bool:
    """Decide whether to call the real LLM planner."""
    context = resolve_planner_context(planner_context)
    mode = str(context.get("useLLM", "auto")).lower()
    has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"))

    if mode in {"true", "1", "yes", "on"}:
        if not has_api_key:
            raise ValueError("USE_LLM_PLANNER is enabled but no LLM API key is set")
        return True

    if mode in {"false", "0", "no", "off"}:
        return False

    return has_api_key


def resolve_planner_context(planner_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge defaults, environment values, and explicit planner context."""
    load_dotenv()
    explicit = planner_context or {}
    context = {**DEFAULT_PLANNER_CONTEXT, **explicit}

    if not explicit.get("modelName"):
        context["modelName"] = os.getenv("MODEL_NAME") or DEFAULT_PLANNER_CONTEXT["modelName"]
    if not explicit.get("openRouterModelName"):
        context["openRouterModelName"] = os.getenv("OPENROUTER_MODEL_NAME") or DEFAULT_PLANNER_CONTEXT[
            "openRouterModelName"
        ]
    if not explicit.get("maxTokens"):
        context["maxTokens"] = int(os.getenv("LLM_MAX_TOKENS") or DEFAULT_PLANNER_CONTEXT["maxTokens"])
    if not explicit.get("provider"):
        context["provider"] = detect_llm_provider()
    if not explicit.get("structuredOutputMode"):
        context["structuredOutputMode"] = os.getenv("LLM_STRUCTURED_OUTPUT_MODE") or DEFAULT_PLANNER_CONTEXT[
            "structuredOutputMode"
        ]
    if "compactInput" not in explicit:
        context["compactInput"] = parse_bool_env("LLM_COMPACT_INPUT", DEFAULT_PLANNER_CONTEXT["compactInput"])
    if "useLLM" not in explicit:
        context["useLLM"] = os.getenv("USE_LLM_PLANNER") or DEFAULT_PLANNER_CONTEXT["useLLM"]

    return context


def detect_llm_provider() -> str:
    provider = (os.getenv("LLM_PROVIDER") or "").lower().strip()
    if provider:
        return provider

    api_key = os.getenv("OPENAI_API_KEY", "")
    if os.getenv("OPENROUTER_API_KEY") or api_key.startswith("sk-or-"):
        return "openrouter"

    return DEFAULT_PLANNER_CONTEXT["provider"]


def parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower().strip() in {"true", "1", "yes", "on"}


def generate_cms_plan(
    html_analysis: dict[str, Any],
    planner_context: dict[str, Any] | None = None,
) -> CmsPlan:
    """Generate a validated CMS plan from deterministic HTML analysis."""
    context = {**DEFAULT_PLANNER_CONTEXT, **(planner_context or {})}
    category = context["componentCategoryPrefix"]
    page_model = build_page_model(html_analysis)
    components = build_shared_section_components(category, html_analysis)
    attributes = build_single_type_attributes(category, html_analysis)
    seed_data = build_seed_data(html_analysis)
    global_blocks = build_global_blocks_plan(html_analysis)
    warnings = build_warnings(html_analysis)

    return CmsPlan(
        pageModel=page_model,
        seo=SeoPlan(enabled=True, component="shared.seo"),
        globalBlocks=global_blocks,
        components=components,
        singleTypeAttributes=attributes,
        seedData=seed_data,
        warnings=warnings,
    )


def build_page_model(html_analysis: dict[str, Any]) -> PageModel:
    title = html_analysis.get("page", {}).get("title", "")
    display_name = page_display_name(title)
    api_name = "landing-page" if "landing" in title.lower() else bounded_slug(display_name or title or "page")
    if not api_name.endswith("page"):
        api_name = f"{api_name}-page"

    if "landing" in title.lower():
        display_name = "Landing Page"

    return PageModel(
        kind="singleType",
        apiName=api_name,
        displayName=display_name,
        singularName=api_name,
        pluralName=pluralize(api_name),
        description=f"CMS single type for {display_name}.",
    )


def build_global_blocks_plan(html_analysis: dict[str, Any]) -> GlobalBlocksPlan:
    global_blocks = html_analysis.get("globalBlocks", {})
    return GlobalBlocksPlan(
        header=GlobalBlockPlan(
            handling="global_single_type",
            apiName="site-header",
            componentPlan="shared.header",
        )
        if global_blocks.get("header")
        else None,
        footer=GlobalBlockPlan(
            handling="global_single_type",
            apiName="site-footer",
            componentPlan="shared.footer",
        )
        if global_blocks.get("footer")
        else None,
    )


def build_shared_section_components(
    category: str,
    html_analysis: dict[str, Any],
) -> list[ComponentPlan]:
    sections = html_analysis.get("candidateSections", [])
    component_builders = {
        "hero": hero_components,
        "features": feature_components,
        "testimonials": testimonial_components,
        "pricing": pricing_components,
        "faq": faq_components,
        "contact": contact_components,
        "quick-answer": quick_answer_components,
        "timeline": timeline_components,
        "process": process_components,
        "results-table": results_table_components,
        "calculator": calculator_components,
        "stats-band": stats_band_components,
        "guarantee": guarantee_components,
        "cta": cta_components,
    }

    components_by_uid: dict[str, ComponentPlan] = {}
    for section in sections:
        file_name = component_file_name_for_section(section)
        builder = component_builders.get(file_name)
        components = builder(category, section) if builder else []
        if not components and is_plannable_section(section):
            components = generic_content_components(category)
        for component in components:
            components_by_uid.setdefault(component.uid, component)

    return list(components_by_uid.values())


def hero_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.hero",
            category=category,
            displayName="Hero",
            fileName="hero",
            fields=[
                FieldPlan(name="eyebrow", type="string"),
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="primary_cta", type="component", component="shared.link", repeatable=False),
                FieldPlan(name="secondary_cta", type="component", component="shared.link", repeatable=False),
                FieldPlan(name="image", type="media", multiple=False, allowedTypes=["images"]),
            ],
        )
    ]


def feature_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    section_fields = section_title_fields(section)
    section_fields.append(FieldPlan(name="items", type="component", component=f"{category}.feature-card", repeatable=True))
    return [
        ComponentPlan(
            uid=f"{category}.features",
            category=category,
            displayName="Features",
            fileName="features",
            fields=section_fields,
        ),
        ComponentPlan(
            uid=f"{category}.feature-card",
            category=category,
            displayName="Feature Card",
            fileName="feature-card",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
            ],
        ),
    ]


def testimonial_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    section_fields = section_title_fields(section)
    section_fields.append(
        FieldPlan(name="items", type="component", component=f"{category}.testimonial-card", repeatable=True)
    )
    return [
        ComponentPlan(
            uid=f"{category}.testimonials",
            category=category,
            displayName="Testimonials",
            fileName="testimonials",
            fields=section_fields,
        ),
        ComponentPlan(
            uid=f"{category}.testimonial-card",
            category=category,
            displayName="Testimonial Card",
            fileName="testimonial-card",
            fields=[
                FieldPlan(name="quote", type="text", required=True),
                FieldPlan(name="author_name", type="string"),
                FieldPlan(name="author_role", type="string"),
            ],
        ),
    ]


def pricing_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    section_fields = section_title_fields(section)
    section_fields.append(FieldPlan(name="items", type="component", component=f"{category}.pricing-card", repeatable=True))
    return [
        ComponentPlan(
            uid=f"{category}.pricing",
            category=category,
            displayName="Pricing",
            fileName="pricing",
            fields=section_fields,
        ),
        ComponentPlan(
            uid=f"{category}.pricing-card",
            category=category,
            displayName="Pricing Card",
            fileName="pricing-card",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="price", type="string"),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="features", type="component", component=f"{category}.pricing-feature", repeatable=True),
                FieldPlan(name="is_highlighted", type="boolean"),
            ],
        ),
        ComponentPlan(
            uid=f"{category}.pricing-feature",
            category=category,
            displayName="Pricing Feature",
            fileName="pricing-feature",
            fields=[
                FieldPlan(name="text", type="string", required=True),
            ],
        ),
    ]


def faq_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    section_fields = section_title_fields(section)
    section_fields.append(FieldPlan(name="items", type="component", component=f"{category}.faq-item", repeatable=True))
    return [
        ComponentPlan(
            uid=f"{category}.faq",
            category=category,
            displayName="FAQ",
            fileName="faq",
            fields=section_fields,
        ),
        ComponentPlan(
            uid=f"{category}.faq-item",
            category=category,
            displayName="FAQ Item",
            fileName="faq-item",
            fields=[
                FieldPlan(name="question", type="string", required=True),
                FieldPlan(name="answer", type="text", required=True),
            ],
        ),
    ]


def contact_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    section_fields = section_title_fields(section)
    section_fields.append(FieldPlan(name="form", type="component", component=f"{category}.form-config", repeatable=False))
    return [
        ComponentPlan(
            uid=f"{category}.contact",
            category=category,
            displayName="Contact",
            fileName="contact",
            fields=section_fields,
        ),
        ComponentPlan(
            uid=f"{category}.form-config",
            category=category,
            displayName="Form Config",
            fileName="form-config",
            fields=[
                FieldPlan(name="action", type="string"),
                FieldPlan(name="method", type="string"),
                FieldPlan(name="submit_label", type="string"),
                FieldPlan(name="fields", type="component", component=f"{category}.form-field", repeatable=True),
            ],
        ),
        ComponentPlan(
            uid=f"{category}.form-field",
            category=category,
            displayName="Form Field",
            fileName="form-field",
            fields=[
                FieldPlan(name="label", type="string"),
                FieldPlan(name="name", type="string", required=True),
                FieldPlan(name="input_type", type="string"),
                FieldPlan(name="required", type="boolean"),
            ],
        ),
    ]


def generic_content_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.{GENERIC_SECTION_COMPONENT}",
            category=category,
            displayName="Content Section",
            fileName=GENERIC_SECTION_COMPONENT,
            fields=[
                FieldPlan(name="eyebrow", type="string"),
                FieldPlan(name="title", type="string"),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="body", type="text"),
                FieldPlan(name="items", type="component", component=f"{category}.{GENERIC_ITEM_COMPONENT}", repeatable=True),
                FieldPlan(name="actions", type="component", component="shared.link", repeatable=True),
                FieldPlan(name="table", type="json"),
                FieldPlan(name="form", type="json"),
                FieldPlan(name="metadata", type="json"),
            ],
        ),
        ComponentPlan(
            uid=f"{category}.{GENERIC_ITEM_COMPONENT}",
            category=category,
            displayName="Content Item",
            fileName=GENERIC_ITEM_COMPONENT,
            fields=[
                FieldPlan(name="title", type="string"),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="text", type="text"),
                FieldPlan(name="value", type="string"),
                FieldPlan(name="label", type="string"),
                FieldPlan(name="period", type="string"),
                FieldPlan(name="saving", type="string"),
                FieldPlan(name="price", type="string"),
                FieldPlan(name="quote", type="text"),
                FieldPlan(name="author_name", type="string"),
                FieldPlan(name="author_role", type="string"),
                FieldPlan(name="features", type="json"),
                FieldPlan(name="image", type="media", multiple=False, allowedTypes=["images"]),
                FieldPlan(name="cta", type="component", component="shared.link", repeatable=False),
            ],
        ),
    ]


def quick_answer_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="quick-answer",
        display_name="Quick Answer",
        item_name="quick-answer-item",
        item_display_name="Quick Answer Item",
    )


def timeline_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="timeline",
        display_name="Timeline",
        item_name="timeline-item",
        item_display_name="Timeline Item",
    )


def process_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="process",
        display_name="Process",
        item_name="process-step",
        item_display_name="Process Step",
    )


def results_table_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="results-table",
        display_name="Results Table",
        item_name="result-item",
        item_display_name="Result Item",
    )


def calculator_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="calculator",
        display_name="Calculator",
        item_name="calculator-result",
        item_display_name="Calculator Result",
    )


def stats_band_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="stats-band",
        display_name="Stats Band",
        item_name="stat-item",
        item_display_name="Stat Item",
    )


def guarantee_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="guarantee",
        display_name="Guarantee",
        item_name="guarantee-item",
        item_display_name="Guarantee Item",
    )


def cta_components(category: str, section: dict[str, Any] | None = None) -> list[ComponentPlan]:
    return rich_content_components(
        category,
        section,
        uid_name="cta",
        display_name="CTA",
        item_name="cta-item",
        item_display_name="CTA Item",
    )


def rich_content_components(
    category: str,
    section: dict[str, Any] | None,
    *,
    uid_name: str,
    display_name: str,
    item_name: str,
    item_display_name: str,
) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.{uid_name}",
            category=category,
            displayName=display_name,
            fileName=uid_name,
            fields=rich_section_fields(category, section, item_name),
        ),
        ComponentPlan(
            uid=f"{category}.{item_name}",
            category=category,
            displayName=item_display_name,
            fileName=item_name,
            fields=rich_item_fields(),
        ),
    ]


def rich_section_fields(category: str, section: dict[str, Any] | None, item_name: str) -> list[FieldPlan]:
    return [
        FieldPlan(name="eyebrow", type="string"),
        FieldPlan(name="title", type="string", required=True),
        FieldPlan(name="description", type="text"),
        FieldPlan(name="body", type="text"),
        FieldPlan(name="items", type="component", component=f"{category}.{item_name}", repeatable=True),
        FieldPlan(name="actions", type="component", component="shared.link", repeatable=True),
        FieldPlan(name="table", type="json"),
        FieldPlan(name="form", type="json"),
        FieldPlan(name="metadata", type="json"),
    ]


def rich_item_fields() -> list[FieldPlan]:
    return [
        FieldPlan(name="period", type="string"),
        FieldPlan(name="title", type="string"),
        FieldPlan(name="description", type="text"),
        FieldPlan(name="text", type="text"),
        FieldPlan(name="value", type="string"),
        FieldPlan(name="label", type="string"),
        FieldPlan(name="saving", type="string"),
        FieldPlan(name="price", type="string"),
        FieldPlan(name="quote", type="text"),
        FieldPlan(name="author_name", type="string"),
        FieldPlan(name="author_role", type="string"),
        FieldPlan(name="features", type="json"),
        FieldPlan(name="image", type="media", multiple=False, allowedTypes=["images"]),
        FieldPlan(name="cta", type="component", component="shared.link", repeatable=False),
    ]


def section_title_fields(section: dict[str, Any] | None = None) -> list[FieldPlan]:
    fields = [FieldPlan(name="title", type="string", required=True)]
    if has_section_description(section):
        fields.append(FieldPlan(name="description", type="text"))
    return fields


def has_section_description(section: dict[str, Any] | None = None) -> bool:
    content = section.get("structuredContent", {}) if isinstance(section, dict) else {}
    return bool(str(content.get("description", "")).strip())


def build_single_type_attributes(
    category: str,
    html_analysis: dict[str, Any],
) -> list[SingleTypeAttribute]:
    attributes = [
        SingleTypeAttribute(
            name="seo",
            type="component",
            component="shared.seo",
            repeatable=False,
        )
    ]

    sections = html_analysis.get("candidateSections", [])
    attribute_names = section_attribute_names(sections)
    for section in sections:
        if not is_plannable_section(section):
            continue
        file_name = component_file_name_for_section(section)
        attributes.append(
            SingleTypeAttribute(
                name=attribute_names.get(section_key(section), attribute_name_for_section(section)),
                type="component",
                component=f"{category}.{file_name}",
                repeatable=False,
                sourceSectionIndex=section.get("index"),
            )
        )

    return attributes


def build_seed_data(html_analysis: dict[str, Any]) -> dict[str, Any]:
    seed_data: dict[str, Any] = {
        "seo": {
            "meta_title": html_analysis.get("page", {}).get("title", ""),
        }
    }

    sections = html_analysis.get("candidateSections", [])
    attribute_names = section_attribute_names(sections)
    for section in sections:
        if not is_plannable_section(section):
            continue
        attr_name = attribute_names.get(section_key(section), attribute_name_for_section(section))
        content = section.get("structuredContent", {})
        hint = section.get("semanticHint", "unknown")

        if hint == "hero":
            seed_data[attr_name] = seed_hero(content)
        elif hint == "feature":
            seed_data[attr_name] = seed_items_section(content)
        elif hint == "testimonial":
            seed_data[attr_name] = seed_testimonials(content)
        elif hint == "pricing":
            seed_data[attr_name] = seed_pricing(content)
        elif hint == "faq":
            seed_data[attr_name] = seed_faq(content)
        elif hint in ("contact", "form"):
            seed_data[attr_name] = seed_contact(content)
        else:
            seed_data[attr_name] = seed_generic_section(section)

    meta_description = first_non_empty(
        seed_data.get("hero", {}).get("description") if isinstance(seed_data.get("hero"), dict) else "",
        seed_data.get("features", {}).get("description") if isinstance(seed_data.get("features"), dict) else "",
        seed_data.get("contact", {}).get("description") if isinstance(seed_data.get("contact"), dict) else "",
    )
    if meta_description:
        seed_data["seo"]["meta_description"] = meta_description

    return seed_data


def seed_hero(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "eyebrow": content.get("eyebrow", ""),
        "title": content.get("title", ""),
        "description": content.get("description", ""),
        "primary_cta": normalize_link(content.get("primaryCta")),
        "secondary_cta": normalize_link(content.get("secondaryCta")),
        "image": content.get("image"),
    }


def seed_items_section(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": content.get("title", ""),
        "description": content.get("description", ""),
        "items": [
            {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            }
            for item in content.get("items", [])
        ],
    }


def seed_testimonials(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": content.get("title", ""),
        "description": content.get("description", ""),
        "items": [
            {
                "quote": item.get("quote", ""),
                "author_name": item.get("authorName", ""),
                "author_role": item.get("authorRole", ""),
            }
            for item in content.get("items", [])
        ],
    }


def seed_pricing(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": content.get("title", ""),
        "description": content.get("description", ""),
        "items": [
            {
                "title": item.get("title", ""),
                "price": item.get("price", ""),
                "description": item.get("description", ""),
                "features": [{"text": feature} for feature in item.get("features", [])],
                "is_highlighted": bool(item.get("isHighlighted")),
            }
            for item in content.get("items", [])
        ],
    }


def seed_faq(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": content.get("title", ""),
        "description": content.get("description", ""),
        "items": [
            {
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
            }
            for item in content.get("items", [])
        ],
    }


def seed_contact(content: dict[str, Any]) -> dict[str, Any]:
    form = content.get("form") or {}
    return {
        "title": content.get("title", ""),
        "description": content.get("description", ""),
        "form": {
            "action": form.get("action", ""),
            "method": form.get("method", ""),
            "submit_label": form.get("submitLabel", ""),
            "fields": [
                {
                    "label": field.get("label", ""),
                    "name": field.get("name", ""),
                    "input_type": field.get("type", ""),
                    "required": bool(field.get("required")),
                }
                for field in form.get("fields", [])
            ],
        },
    }


def seed_generic_section(section: dict[str, Any]) -> dict[str, Any]:
    content = section.get("structuredContent", {}) if isinstance(section, dict) else {}
    title = first_non_empty(content.get("title"), section.get("heading"), first_subheading(section))
    description = first_non_empty(content.get("description"), "")
    buttons = section.get("buttons", []) if isinstance(section.get("buttons"), list) else []

    return {
        "eyebrow": first_non_empty(content.get("eyebrow"), section_eyebrow(section, title)),
        "title": title,
        "description": description,
        "body": first_non_empty(content.get("body"), section.get("textPreview"), description),
        "items": generic_items_from_section(section),
        "actions": [link for link in (normalize_link(button) for button in buttons) if link],
        "table": first_non_empty_json(section.get("table"), content.get("table")),
        "form": first_non_empty_json(section.get("forms"), content.get("form")),
        "metadata": {
            "semanticHint": section.get("semanticHint", "unknown"),
            "sourceSectionIndex": section.get("index"),
            "id": section.get("id", ""),
            "classes": section.get("classes", []),
        },
    }


def generic_items_from_section(section: dict[str, Any]) -> list[dict[str, Any]]:
    content = section.get("structuredContent", {}) if isinstance(section, dict) else {}
    content_items = content.get("items") if isinstance(content, dict) else None
    if isinstance(content_items, list):
        items = [
            seed_generic_item(item)
            for item in content_items
            if isinstance(item, dict) and has_meaningful_item_seed(item)
        ]
        if items:
            return items

    group = best_repeated_group(section.get("repeatedGroups", []))
    if not group:
        return []

    return [
        seed_generic_item(item)
        for item in group.get("sampleItems", [])
        if isinstance(item, dict) and has_meaningful_item_seed(item)
    ]


def best_repeated_group(groups: Any) -> dict[str, Any] | None:
    if not isinstance(groups, list):
        return None

    scored_groups = [
        (generic_group_score(group), group)
        for group in groups
        if isinstance(group, dict)
    ]
    scored_groups = [(score, group) for score, group in scored_groups if score > 0]
    if not scored_groups:
        return None
    scored_groups.sort(key=lambda item: item[0], reverse=True)
    return scored_groups[0][1]


def generic_group_score(group: dict[str, Any]) -> int:
    class_name = str(group.get("className") or "").lower()
    ignored_classes = {"rv", "d1", "d2", "d3", "d4", "d5"}
    ignored_fragments = ("orb", "bar", "fill", "num", "key", "stars", "av")
    if class_name in ignored_classes or any(fragment in class_name for fragment in ignored_fragments):
        return 0

    fields = group.get("fieldsDetected", [])
    sample_items = group.get("sampleItems", [])
    sample_score = 0
    if isinstance(sample_items, list):
        sample_score = sum(1 for item in sample_items if isinstance(item, dict) and has_meaningful_item_seed(item))
    return len(fields if isinstance(fields, list) else []) * 2 + sample_score


def seed_generic_item(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get("text") or "").strip()
    value = str(item.get("value") or "").strip()
    label = str(item.get("label") or "").strip()
    if not value and not label and text:
        value, label = split_value_label(text)

    return {
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "text": text,
        "value": value,
        "label": label,
        "period": item.get("period", ""),
        "saving": item.get("saving", ""),
        "price": item.get("price", ""),
        "quote": item.get("quote", ""),
        "author_name": item.get("authorName", ""),
        "author_role": item.get("authorRole", ""),
        "features": item.get("features", []),
        "image": item.get("image"),
        "cta": normalize_link(item.get("cta")),
    }


def has_meaningful_item_seed(item: dict[str, Any]) -> bool:
    meaningful_keys = ("title", "description", "text", "value", "label", "quote", "authorName", "authorRole")
    return any(str(item.get(key) or "").strip() for key in meaningful_keys) or bool(item.get("image") or item.get("cta"))


def section_eyebrow(section: dict[str, Any], title: str) -> str:
    subheading = first_subheading(section)
    if subheading and subheading != title:
        return subheading
    return ""


def first_subheading(section: dict[str, Any]) -> str:
    subheadings = section.get("subheadings")
    if not isinstance(subheadings, list):
        return ""
    for subheading in subheadings:
        if isinstance(subheading, dict):
            text = str(subheading.get("text") or "").strip()
            if text:
                return text
    return ""


def first_non_empty_json(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None


def normalize_link(value: dict[str, Any] | None) -> dict[str, str] | None:
    if not value:
        return None
    return {
        "text": value.get("text", ""),
        "url": value.get("href", ""),
    }


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def build_warnings(html_analysis: dict[str, Any]) -> list[str]:
    fallback_indexes = [
        str(section.get("index"))
        for section in html_analysis.get("candidateSections", [])
        if is_generic_fallback_section(section)
    ]
    if not fallback_indexes:
        return []
    return [
        "Mapped non-canonical sections to the generic content-section component: "
        + ", ".join(fallback_indexes)
    ]


def component_file_name_for_section(section: dict[str, Any]) -> str:
    hint = str(section.get("semanticHint") or "unknown")
    hinted_file_name = CANONICAL_COMPONENT_BY_HINT.get(hint)
    if hinted_file_name:
        return hinted_file_name

    section_type = snake_case(str(section.get("sectionType") or ""))
    if section_type in CANONICAL_COMPONENT_BY_SECTION_TYPE:
        return CANONICAL_COMPONENT_BY_SECTION_TYPE[section_type]

    for fragment, file_name in SEMANTIC_COMPONENT_TYPE_FRAGMENTS:
        if fragment in section_type:
            return file_name

    if has_table_content(section):
        return "results-table"
    if has_quick_answer_signal(section):
        return "quick-answer"
    if has_calculator_signal(section):
        return "calculator"
    if has_trust_stats_signal(section):
        return "stats-band"
    if has_guarantee_signal(section):
        return "guarantee"

    return GENERIC_SECTION_COMPONENT


def has_table_content(section: dict[str, Any]) -> bool:
    content = section.get("structuredContent") if isinstance(section.get("structuredContent"), dict) else {}
    table = section.get("table") or content.get("table")
    return isinstance(table, dict) and bool(table.get("headers") or table.get("rows"))


def has_calculator_signal(section: dict[str, Any]) -> bool:
    source = section_signal_text(section)
    return "calculator" in source or "calc-section" in source


def has_quick_answer_signal(section: dict[str, Any]) -> bool:
    source = section_signal_text(section)
    return bool(re.search(r"\bquick answer\b", source)) or any(
        fragment in source
        for fragment in ("answer-box", "answer_box", "aeo-answer", "aeo_answer")
    )


def has_trust_stats_signal(section: dict[str, Any]) -> bool:
    source = section_signal_text(section)
    return any(fragment in source for fragment in ("trust-band", "trust_metric", "trust-metric", "stats-band"))


def has_guarantee_signal(section: dict[str, Any]) -> bool:
    source = section_signal_text(section)
    return bool(re.search(r"\bguarantee\b", source)) or "refund the shortfall" in source or "pay the difference" in source


def section_signal_text(section: dict[str, Any]) -> str:
    content = section.get("structuredContent") if isinstance(section.get("structuredContent"), dict) else {}
    classes = " ".join(str(class_name or "") for class_name in section.get("classes", []) if isinstance(class_name, str))
    values = [
        section.get("semanticHint", ""),
        section.get("sectionType", ""),
        section.get("id", ""),
        classes,
        content.get("eyebrow", ""),
        content.get("title", ""),
        content.get("description", ""),
        first_subheading(section),
    ]
    return " ".join(str(value or "") for value in values).lower()


def attribute_name_for_section(section: dict[str, Any]) -> str:
    hint = section.get("semanticHint", "section")
    if component_file_name_for_section(section) == "quick-answer":
        return "quick_answer"
    if hint == "feature":
        return "features"
    if hint == "testimonial":
        return "testimonials"
    if hint in STABLE_ATTRIBUTE_HINTS and hint not in {"form"}:
        return snake_case(hint)

    base = first_non_empty(
        section.get("id"),
        section.get("sectionType"),
        (section.get("structuredContent") or {}).get("title") if isinstance(section.get("structuredContent"), dict) else "",
        section.get("heading"),
        first_subheading(section),
        meaningful_class_name(section),
        f"section_{section.get('index', '')}",
    )
    return bounded_snake_case(base)


def section_attribute_names(sections: list[dict[str, Any]]) -> dict[int, str]:
    names: dict[int, str] = {}
    used: set[str] = set()
    for section in sections:
        if not is_plannable_section(section):
            continue
        base_name = attribute_name_for_section(section)
        name = unique_name(base_name, used, fallback_suffix=str(section.get("index", "")))
        names[section_key(section)] = name
    return names


def section_key(section: dict[str, Any]) -> int:
    index = section.get("index")
    return index if isinstance(index, int) else id(section)


def unique_name(base_name: str, used: set[str], *, fallback_suffix: str = "") -> str:
    name = ensure_snake_identifier(base_name)
    if name not in used:
        used.add(name)
        return name

    suffix = snake_case(fallback_suffix) if fallback_suffix else "section"
    suffix = suffix or "section"
    candidate = ensure_snake_identifier(f"{name}_{suffix}")
    counter = 2
    while candidate in used:
        candidate = ensure_snake_identifier(f"{name}_{counter}")
        counter += 1
    used.add(candidate)
    return candidate


def is_plannable_section(section: dict[str, Any]) -> bool:
    return section.get("semanticHint") not in LAYOUT_SECTION_HINTS


def is_generic_fallback_section(section: dict[str, Any]) -> bool:
    return is_plannable_section(section) and component_file_name_for_section(section) == GENERIC_SECTION_COMPONENT


def meaningful_class_name(section: dict[str, Any]) -> str:
    classes = section.get("classes")
    if not isinstance(classes, list):
        return ""
    ignored = {"container", "wrapper", "row", "col", "grid", "inner", "content", "layout", "ps", "rv"}
    for class_name in classes:
        normalized = str(class_name or "").strip().lower()
        if normalized and normalized not in ignored:
            return normalized
    return ""


def page_display_name(title: str) -> str:
    separators = (" | ", " — ", " – ", " - ")
    positions = [(title.find(separator), separator) for separator in separators if separator in title]
    if positions:
        _, separator = min(positions, key=lambda item: item[0])
        return title.split(separator, 1)[0].strip() or title.strip() or "Landing Page"
    return title.strip() or "Landing Page"


def bounded_slug(value: str, max_length: int = MAX_API_NAME_LENGTH) -> str:
    words = slugify(value).split("-")
    result_words: list[str] = []
    for word in words:
        candidate = "-".join([*result_words, word]) if result_words else word
        if len(candidate) > max_length:
            break
        result_words.append(word)
    return "-".join(result_words) or "page"


def bounded_snake_case(value: str, max_length: int = MAX_ATTRIBUTE_NAME_LENGTH) -> str:
    words = snake_case(value).split("_")
    result_words: list[str] = []
    for word in words:
        candidate = "_".join([*result_words, word]) if result_words else word
        if len(candidate) > max_length:
            break
        result_words.append(word)
    return ensure_snake_identifier("_".join(result_words) or "section")


def ensure_snake_identifier(value: str) -> str:
    result = snake_case(value)
    if not result or not result[0].isalpha():
        result = f"section_{result}" if result else "section"
    return result


def split_value_label(text: str) -> tuple[str, str]:
    match = re.match(r"^([₹$]?[0-9][0-9,]*(?:\.\d+)?%?|[0-9]+(?:\.\d+)?[A-Za-z]+)\s+(.+)$", text)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "page"


def pluralize(value: str) -> str:
    if value.endswith("y"):
        return f"{value[:-1]}ies"
    if value.endswith("s"):
        return f"{value}es"
    return f"{value}s"


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return value.strip("_").lower() or "section"
