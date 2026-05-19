"""Deterministic HTML inspection for candidate section extraction.

This module intentionally does not decide final CMS component names. It turns
messy HTML into cleaner candidate section JSON for a future LLM classifier.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from bs4 import Tag

from src.html_parser import (
    clean_text,
    extract_buttons,
    extract_images,
    extract_page_title,
    find_page_root,
    get_classes,
    load_html_from_file,
    parse_html,
)


SECTION_KEYWORDS = (
    "hero",
    "intro",
    "features",
    "feature",
    "services",
    "service",
    "faq",
    "cta",
    "testimonial",
    "testimonials",
    "pricing",
    "process",
    "timeline",
    "case",
    "case-study",
    "comparison",
    "calculator",
    "proof",
    "benefit",
    "contact",
    "demo",
    "form",
    "table",
)

WRAPPER_KEYWORDS = (
    "container",
    "wrapper",
    "row",
    "col",
    "grid",
    "inner",
    "content",
    "layout",
)

REPEATED_GROUP_IGNORE_CLASSES = set(WRAPPER_KEYWORDS)
SECTION_TAGS = ("section", "article", "header", "footer")
FORM_FIELD_TAGS = ("input", "textarea", "select")


def analyze_html_file(file_path: str | Path) -> dict[str, Any]:
    """Analyze an HTML file and return clean candidate sections for LLM input."""
    html = load_html_from_file(file_path)
    soup = parse_html(html)
    root = find_page_root(soup)
    candidates = find_candidate_sections(root)

    sections = [
        build_candidate_section(index, candidate)
        for index, candidate in enumerate(candidates, start=1)
    ]

    return {
        "page": {
            "title": extract_page_title(soup),
            "rootTag": getattr(root, "name", "document"),
            "sectionCount": len(sections),
        },
        "candidateSections": sections,
    }


def find_candidate_sections(root: Tag) -> list[Tag]:
    """Find likely top-level content sections while skipping layout wrappers."""
    candidates: list[Tag] = []

    for child in root.find_all(recursive=False):
        if not isinstance(child, Tag):
            continue

        if is_candidate_section(child):
            candidates.append(child)
            continue

        for nested in child.find_all(SECTION_TAGS + ("div",), recursive=False):
            if is_candidate_section(nested):
                candidates.append(nested)

    return dedupe_tags(candidates)


def is_candidate_section(tag: Tag) -> bool:
    if tag.name in ("header", "footer", "section"):
        return has_meaningful_content(tag)

    if tag.name == "article":
        return is_section_like(tag) and not is_repeated_item(tag)

    if tag.name == "div":
        if is_wrapper(tag) and not has_strong_section_signal(tag):
            return False
        return has_strong_section_signal(tag)

    return False


def has_meaningful_content(tag: Tag) -> bool:
    return bool(clean_text(tag.get_text(" ")))


def is_section_like(tag: Tag) -> bool:
    source = source_text(tag)
    return any(keyword in source for keyword in SECTION_KEYWORDS)


def has_strong_section_signal(tag: Tag) -> bool:
    heading = tag.find(["h1", "h2", "h3"])
    source = source_text(tag)
    has_keyword = any(keyword in source for keyword in SECTION_KEYWORDS)
    has_enough_text = len(clean_text(tag.get_text(" "))) >= 80
    return bool(heading and (has_keyword or has_enough_text))


def is_wrapper(tag: Tag) -> bool:
    classes = get_classes(tag)
    return any(cls.lower() in WRAPPER_KEYWORDS for cls in classes)


def is_repeated_item(tag: Tag) -> bool:
    classes = " ".join(get_classes(tag)).lower()
    return any(word in classes for word in ("card", "item", "tile"))


def source_text(tag: Tag) -> str:
    classes = " ".join(get_classes(tag))
    values = [tag.name or "", clean_text(tag.get("id")), classes, clean_text(tag.get_text(" "))]
    return " ".join(values).lower()


def build_candidate_section(index: int, candidate: Tag) -> dict[str, Any]:
    heading = extract_main_heading(candidate)
    table = extract_table(candidate)
    repeated_groups = detect_repeated_groups(candidate)
    images = extract_images(candidate)
    buttons = extract_buttons(candidate)

    return {
        "index": index,
        "semanticHint": infer_semantic_hint(candidate),
        "tag": candidate.name,
        "id": clean_text(candidate.get("id")),
        "classes": get_classes(candidate),
        "heading": heading["text"],
        "headingLevel": heading["level"],
        "subheadings": extract_subheadings(candidate),
        "textPreview": extract_text_preview(candidate),
        "buttons": buttons,
        "images": images,
        "hasButtons": bool(buttons),
        "hasCards": bool(repeated_groups),
        "hasTable": table is not None,
        "table": table,
        "hasFaqPattern": detect_faq_pattern(candidate),
        "hasForm": detect_form(candidate),
        "hasImages": bool(images),
        "childBlockCount": count_child_blocks(candidate),
        "repeatedGroups": repeated_groups,
    }


def extract_main_heading(tag: Tag) -> dict[str, str]:
    heading = tag.find(["h1", "h2", "h3"])
    if not heading:
        return {"text": "", "level": ""}
    return {"text": clean_text(heading.get_text(" ")), "level": heading.name}


def extract_subheadings(tag: Tag) -> list[dict[str, str]]:
    subheadings = []
    for heading in tag.find_all(["h2", "h3", "h4"]):
        text = clean_text(heading.get_text(" "))
        if text:
            subheadings.append({"text": text, "level": heading.name})
    return subheadings


def extract_text_preview(tag: Tag, limit: int = 300) -> str:
    return clean_text(tag.get_text(" "))[:limit]


def extract_table(tag: Tag) -> dict[str, Any] | None:
    table = tag.find("table")
    if not table:
        return None

    headers = [clean_text(th.get_text(" ")) for th in table.find_all("th")]
    rows = table.find_all("tr")
    row_count = max(len(rows) - 1, 0) if headers else len(rows)

    return {
        "headers": [header for header in headers if header],
        "rowCount": row_count,
    }


def detect_faq_pattern(tag: Tag) -> bool:
    structural = " ".join([clean_text(tag.get("id")), " ".join(get_classes(tag))]).lower()
    heading_text = " ".join(
        clean_text(heading.get_text(" "))
        for heading in tag.find_all(["h1", "h2", "h3"], recursive=False)
    ).lower()

    if "faq" in structural or "frequently asked" in heading_text:
        return True
    if tag.find_all("details"):
        return True

    question_like_headings = [
        heading
        for heading in tag.find_all(["h2", "h3", "h4"])
        if "?" in clean_text(heading.get_text(" "))
    ]
    return len(question_like_headings) >= 2


def detect_form(tag: Tag) -> bool:
    return bool(tag.find("form") or tag.find_all(FORM_FIELD_TAGS))


def detect_repeated_groups(tag: Tag) -> list[dict[str, Any]]:
    class_counter: Counter[str] = Counter()
    elements_by_class: dict[str, list[Tag]] = {}

    for element in tag.find_all(["div", "li", "article"]):
        for class_name in get_classes(element):
            normalized = class_name.lower()
            class_counter[normalized] += 1
            elements_by_class.setdefault(normalized, []).append(element)

    groups = []
    for class_name, count in class_counter.items():
        if count < 2 or class_name in REPEATED_GROUP_IGNORE_CLASSES:
            continue

        sample = elements_by_class[class_name][0]
        groups.append(
            {
                "className": class_name,
                "selectorHint": f".{class_name}",
                "count": count,
                "sampleText": extract_text_preview(sample, limit=200),
                "fieldsDetected": infer_repeated_group_fields(sample),
                "hasHeading": bool(sample.find(["h3", "h4"])),
                "hasDescription": bool(sample.find("p")),
                "hasImage": bool(sample.find("img")),
            }
        )

    return groups


def infer_repeated_group_fields(tag: Tag) -> list[str]:
    fields = []
    if tag.find(["h3", "h4"]):
        fields.append("title")
    if tag.find("p"):
        fields.append("description")
    if tag.find("img"):
        fields.append("image")
    if tag.find(["a", "button"]):
        fields.append("cta")
    if tag.find("blockquote"):
        fields.append("quote")
    if "$" in tag.get_text(" "):
        fields.append("price")
    return fields


def infer_semantic_hint(tag: Tag) -> str:
    structural = " ".join([tag.name or "", clean_text(tag.get("id")), " ".join(get_classes(tag))]).lower()
    heading = extract_main_heading(tag)["text"].lower()

    for keyword in SECTION_KEYWORDS:
        if contains_keyword(structural, keyword) or contains_keyword(heading, keyword):
            return normalize_hint(keyword)

    if tag.name == "header":
        return "header"
    if tag.name == "footer":
        return "footer"
    if tag.find("form"):
        return "form"
    if tag.find("table"):
        return "table"

    return "unknown"


def contains_keyword(text: str, keyword: str) -> bool:
    if "-" in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def normalize_hint(keyword: str) -> str:
    normalized = keyword.replace("-", "_")
    plural_map = {
        "features": "feature",
        "services": "service",
        "testimonials": "testimonial",
    }
    return plural_map.get(normalized, normalized)


def count_child_blocks(tag: Tag) -> int:
    return len([child for child in tag.find_all(recursive=False) if isinstance(child, Tag)])


def dedupe_tags(tags: list[Tag]) -> list[Tag]:
    seen = set()
    result = []
    for tag in tags:
        identity = id(tag)
        if identity not in seen:
            seen.add(identity)
            result.append(tag)
    return result
