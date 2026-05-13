"""Deterministic page section detection for the notebook MVP."""

from __future__ import annotations

import re
from typing import Any


SECTION_RULES = [
    {
        "section_type": "header",
        "keywords": ("header", "site-header"),
        "fields": ("brand", "navigation_links", "cta_link"),
    },
    {
        "section_type": "navbar",
        "keywords": ("nav", "navbar", "navigation", "nav-links"),
        "fields": ("brand", "navigation_links"),
    },
    {
        "section_type": "hero",
        "keywords": ("hero", "headline", "subtitle", "start free", "view plans"),
        "fields": ("heading", "subheading", "cta_links", "image"),
    },
    {
        "section_type": "features",
        "keywords": ("features", "feature", "feature-card", "everything your team needs"),
        "fields": ("heading", "description", "feature_cards"),
    },
    {
        "section_type": "testimonials",
        "keywords": ("testimonials", "testimonial", "trusted by", "blockquote"),
        "fields": ("heading", "quotes", "authors", "roles"),
    },
    {
        "section_type": "pricing",
        "keywords": ("pricing", "price", "plans", "starter", "growth", "scale"),
        "fields": ("heading", "plan_cards", "price", "features"),
    },
    {
        "section_type": "faq",
        "keywords": ("faq", "frequently asked", "questions", "faq-item"),
        "fields": ("questions", "answers"),
    },
    {
        "section_type": "contact_form",
        "keywords": ("contact", "form", "request demo", "talk to our team"),
        "fields": ("heading", "description", "form_fields", "submit_button"),
    },
    {
        "section_type": "footer",
        "keywords": ("footer", "site-footer", "copyright"),
        "fields": ("brand", "footer_links", "copyright"),
    },
]


def detect_common_sections(dom_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect common landing page sections from a DOM summary."""
    detected = []

    for section in dom_summary.get("sections", []):
        section_type = classify_section(section)
        if not section_type:
            continue

        detected.append(
            {
                "section_type": section_type,
                "confidence": score_section(section, section_type),
                "source": build_source(section),
                "title": section.get("title", ""),
                "fields_detected": infer_fields(section_type, dom_summary),
            }
        )

    return dedupe_sections(detected)


def classify_section(section: dict[str, Any]) -> str | None:
    tag = section.get("tag", "")
    section_id = section.get("id", "")
    classes = section.get("classes", [])
    class_text = " ".join(classes)
    title = section.get("title", "")
    text_preview = section.get("text_preview", "")
    structural_text = f"{tag} {section_id} {class_text}".lower()
    content_text = f"{title} {text_preview}".lower()

    if tag == "header":
        return "header"
    if tag == "footer":
        return "footer"
    if tag == "nav" and "footer" not in structural_text:
        return "navbar"

    for rule in SECTION_RULES:
        if any(keyword in structural_text for keyword in rule["keywords"]):
            return rule["section_type"]

    for rule in SECTION_RULES:
        if any(contains_keyword(content_text, keyword) for keyword in rule["keywords"]):
            return rule["section_type"]

    return None


def score_section(section: dict[str, Any], section_type: str) -> float:
    tag = section.get("tag", "")
    section_id = section.get("id", "").lower()
    classes = " ".join(section.get("classes", [])).lower()
    title = section.get("title", "").lower()
    text_preview = section.get("text_preview", "").lower()
    haystack = f"{section_id} {classes} {title} {text_preview}"

    confidence = 0.55

    if tag == section_type:
        confidence += 0.2
    if section_id == section_type or section_type in section_id:
        confidence += 0.25
    if section_type in classes:
        confidence += 0.2
    if section_type.replace("_", " ") in title:
        confidence += 0.1
    if any(keyword in haystack for keyword in keywords_for(section_type)):
        confidence += 0.1

    if section_type == "contact_form" and ("form" in classes or "request demo" in text_preview):
        confidence += 0.15

    return min(round(confidence, 2), 0.98)


def keywords_for(section_type: str) -> tuple[str, ...]:
    for rule in SECTION_RULES:
        if rule["section_type"] == section_type:
            return rule["keywords"]
    return ()


def contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword or "-" in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def infer_fields(section_type: str, dom_summary: dict[str, Any]) -> list[str]:
    for rule in SECTION_RULES:
        if rule["section_type"] == section_type:
            fields = list(rule["fields"])
            break
    else:
        fields = []

    if section_type == "contact_form" and dom_summary.get("forms"):
        form_fields = [
            field.get("name")
            for form in dom_summary["forms"]
            for field in form.get("fields", [])
            if field.get("name")
        ]
        fields.extend(form_fields)

    return dedupe_strings(fields)


def build_source(section: dict[str, Any]) -> str:
    source_parts = [f"tag:{section.get('tag', '')}"]
    if section.get("id"):
        source_parts.append(f"id:{section['id']}")
    if section.get("classes"):
        source_parts.append(f"classes:{' '.join(section['classes'])}")
    return " ".join(source_parts)


def dedupe_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_type: dict[str, dict[str, Any]] = {}

    for section in sections:
        section_type = section["section_type"]
        current = best_by_type.get(section_type)
        if current is None or section["confidence"] > current["confidence"]:
            best_by_type[section_type] = section

    preferred_order = [
        "header",
        "navbar",
        "hero",
        "features",
        "testimonials",
        "pricing",
        "faq",
        "contact_form",
        "footer",
    ]
    return [
        best_by_type[section_type]
        for section_type in preferred_order
        if section_type in best_by_type
    ]


def dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
