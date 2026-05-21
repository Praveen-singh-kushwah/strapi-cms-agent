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
    repair_component_uids(payload)
    repair_section_attribute_names(payload)
    repair_dynamic_sections_attribute(payload)
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


def repair_component_references(items: Any, replacements: dict[str, str]) -> None:
    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(item, dict):
            continue
        component = item.get("component")
        if component in replacements:
            item["component"] = replacements[component]


def repair_section_attribute_names(payload: dict[str, Any]) -> None:
    attributes = payload.get("singleTypeAttributes", [])
    seed_data = payload.get("seedData", {})
    if not isinstance(attributes, list) or not isinstance(seed_data, dict):
        return

    canonical_names = {"hero", "features", "testimonials", "pricing", "faq", "contact"}
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
    canonical_names = ("hero", "features", "testimonials", "pricing", "faq", "contact")
    section_seed_names = [name for name in canonical_names if seed_data.get(name) is not None]
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
    source_indexes = {
        "hero": 1,
        "features": 2,
        "testimonials": 3,
        "pricing": 4,
        "faq": 5,
        "contact": 6,
    }
    return source_indexes.get(section_name)


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
    api_name = "landing-page" if "landing" in title.lower() else slugify(title or "page")
    if not api_name.endswith("page"):
        api_name = f"{api_name}-page"

    display_name = title.split(" - ")[0].strip() or "Landing Page"
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
        "feature": feature_components,
        "testimonial": testimonial_components,
        "pricing": pricing_components,
        "faq": faq_components,
        "contact": contact_components,
        "form": contact_components,
    }

    components_by_uid: dict[str, ComponentPlan] = {}
    for section in sections:
        hint = section.get("semanticHint", "unknown")
        builder = component_builders.get(hint)
        if not builder:
            continue
        for component in builder(category):
            components_by_uid.setdefault(component.uid, component)

    return list(components_by_uid.values())


def hero_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.hero-section",
            category=category,
            displayName="Hero Section",
            fileName="hero-section",
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


def feature_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.features-section",
            category=category,
            displayName="Features Section",
            fileName="features-section",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="items", type="component", component=f"{category}.feature-card", repeatable=True),
            ],
        ),
        ComponentPlan(
            uid=f"{category}.feature-card",
            category=category,
            displayName="Feature Card",
            fileName="feature-card",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="image", type="media", multiple=False, allowedTypes=["images"]),
                FieldPlan(name="cta", type="component", component="shared.link", repeatable=False),
            ],
        ),
    ]


def testimonial_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.testimonials-section",
            category=category,
            displayName="Testimonials Section",
            fileName="testimonials-section",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="items", type="component", component=f"{category}.testimonial-card", repeatable=True),
            ],
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


def pricing_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.pricing-section",
            category=category,
            displayName="Pricing Section",
            fileName="pricing-section",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="items", type="component", component=f"{category}.pricing-card", repeatable=True),
            ],
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


def faq_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.faq-section",
            category=category,
            displayName="FAQ Section",
            fileName="faq-section",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="items", type="component", component=f"{category}.faq-item", repeatable=True),
            ],
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


def contact_components(category: str) -> list[ComponentPlan]:
    return [
        ComponentPlan(
            uid=f"{category}.contact-section",
            category=category,
            displayName="Contact Section",
            fileName="contact-section",
            fields=[
                FieldPlan(name="title", type="string", required=True),
                FieldPlan(name="description", type="text"),
                FieldPlan(name="form", type="component", component=f"{category}.form-config", repeatable=False),
            ],
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

    component_by_hint = {
        "hero": "hero-section",
        "feature": "features-section",
        "testimonial": "testimonials-section",
        "pricing": "pricing-section",
        "faq": "faq-section",
        "contact": "contact-section",
        "form": "contact-section",
    }

    for section in html_analysis.get("candidateSections", []):
        hint = section.get("semanticHint", "unknown")
        file_name = component_by_hint.get(hint)
        if not file_name:
            continue
        attributes.append(
            SingleTypeAttribute(
                name=attribute_name_for_section(section),
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

    for section in html_analysis.get("candidateSections", []):
        attr_name = attribute_name_for_section(section)
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
                "image": item.get("image"),
                "cta": normalize_link(item.get("cta")),
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


def normalize_link(value: dict[str, Any] | None) -> dict[str, str] | None:
    if not value:
        return None
    return {
        "text": value.get("text", ""),
        "url": value.get("href", ""),
    }


def build_warnings(html_analysis: dict[str, Any]) -> list[str]:
    warnings = []
    for section in html_analysis.get("candidateSections", []):
        if section.get("semanticHint") == "unknown":
            warnings.append(
                f"Section {section.get('index')} could not be mapped to a known component type."
            )
    return warnings


def attribute_name_for_section(section: dict[str, Any]) -> str:
    hint = section.get("semanticHint", "section")
    section_id = section.get("id") or hint
    if hint == "feature":
        return "features"
    if hint == "testimonial":
        return "testimonials"
    return snake_case(section_id)


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
