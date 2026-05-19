"""LLM section planner foundation for Strapi CMS plans.

The deterministic planner in this file mirrors the JSON shape expected from a
future LLM call. It lets the notebook validate the CMS planning contract before
LangGraph/LangChain are introduced.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

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
}


def llm_section_planner_node(state: AgentState) -> AgentState:
    """LangGraph-compatible node shape for section planning.

    This currently uses the deterministic planner so the flow can run locally
    without API keys. A real LLM call can replace generate_cms_plan while keeping
    the same CmsPlan validation contract.
    """
    try:
        html_analysis = state["html_analysis"]
        context = {**DEFAULT_PLANNER_CONTEXT, **state.get("planner_context", {})}
        cms_plan = generate_cms_plan(html_analysis, context)
        return {**state, "cms_plan": cms_plan.model_dump()}
    except Exception as exc:  # pragma: no cover - notebook-friendly error capture
        errors = [*state.get("errors", []), str(exc)]
        return {**state, "errors": errors}


def build_section_planner_prompt(
    html_analysis: dict[str, Any],
    planner_context: dict[str, Any] | None = None,
) -> str:
    """Build the strict prompt that the future LLM planner should receive."""
    context = {**DEFAULT_PLANNER_CONTEXT, **(planner_context or {})}
    return f"""You are a Strapi CMS architect.

You will receive structured HTML section analysis from a deterministic parser.

Your task:
Convert it into a Strapi CMS plan.

Rules:
- Output only valid JSON matching the CmsPlan schema.
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
{json.dumps(html_analysis, indent=2)}
"""


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
