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
- Include warnings when uncertain.

Planner context:
{json.dumps(context, indent=2)}

HTML analysis:
{json.dumps(prompt_analysis, indent=2)}
"""


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

    choice = completion.choices[0]
    content = choice.message.content
    if not content:
        raise ValueError(
            "OpenRouter planner returned an empty response "
            f"(finish_reason={choice.finish_reason}, message={choice.message.model_dump()})"
        )

    return CmsPlan.model_validate_json(content)


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
