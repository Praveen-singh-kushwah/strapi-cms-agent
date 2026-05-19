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
    extract_forms,
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
        "globalBlocks": extract_global_blocks(soup),
        "candidateSections": sections,
    }


def extract_global_blocks(soup: Tag) -> dict[str, Any]:
    """Extract layout-level blocks separately from main page sections."""
    header = soup.find("header")
    footer = soup.find("footer")

    return {
        "header": extract_header_block(header) if header else None,
        "footer": extract_footer_block(footer) if footer else None,
    }


def extract_header_block(header: Tag) -> dict[str, Any]:
    links = extract_buttons(header)
    brand_link = header.find("a")
    brand = clean_text(brand_link.get_text(" ")) if brand_link else ""
    navigation_links = links[1:] if links and links[0]["text"] == brand else links
    cta = navigation_links[-1] if navigation_links else None

    return {
        "tag": header.name,
        "id": clean_text(header.get("id")),
        "classes": get_classes(header),
        "brand": brand,
        "navigationLinks": navigation_links[:-1] if cta else navigation_links,
        "cta": cta,
        "textPreview": extract_text_preview(header),
    }


def extract_footer_block(footer: Tag) -> dict[str, Any]:
    links = extract_buttons(footer)
    paragraphs = [clean_text(paragraph.get_text(" ")) for paragraph in footer.find_all("p")]
    brand = clean_text(footer.find("a").get_text(" ")) if footer.find("a") else ""
    footer_links = links[1:] if links and links[0]["text"] == brand else links

    return {
        "tag": footer.name,
        "id": clean_text(footer.get("id")),
        "classes": get_classes(footer),
        "brand": brand,
        "description": paragraphs[0] if paragraphs else "",
        "links": footer_links,
        "copyright": next((text for text in paragraphs if "copyright" in text.lower()), ""),
        "textPreview": extract_text_preview(footer),
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
    forms = extract_forms(candidate)
    has_form = detect_form(candidate)
    has_faq_pattern = detect_faq_pattern(candidate)

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
        "structuredContent": extract_structured_content(candidate),
        "structureSignals": {
            "hasButtons": bool(buttons),
            "hasCards": bool(repeated_groups),
            "hasTable": table is not None,
            "hasFaqPattern": has_faq_pattern,
            "hasForm": has_form,
            "hasImages": bool(images),
            "childBlockCount": count_child_blocks(candidate),
        },
        "table": table,
        "forms": forms,
        "repeatedGroups": repeated_groups,
    }


def extract_structured_content(tag: Tag) -> dict[str, Any]:
    hint = infer_semantic_hint(tag)
    base_content = extract_section_title_description(tag)

    if hint == "hero":
        return {**base_content, **extract_hero_content(tag)}
    if hint == "pricing":
        return {**base_content, "items": extract_pricing_items(tag)}
    if hint == "faq":
        return {**base_content, "items": extract_faq_items(tag)}
    if hint == "testimonial":
        return {**base_content, "items": extract_testimonial_items(tag)}
    if hint == "feature":
        return {**base_content, "items": extract_card_items(tag)}
    if hint in ("contact", "form"):
        return {**base_content, "form": extract_form_details(tag)}

    return base_content


def extract_section_title_description(tag: Tag) -> dict[str, str]:
    heading = extract_main_heading(tag)["text"]
    description = ""

    for paragraph in tag.find_all("p", recursive=False):
        text = clean_text(paragraph.get_text(" "))
        if text:
            description = text
            break

    if not description:
        for child in tag.find_all(recursive=False):
            if child.name in ("div", "article"):
                paragraph = child.find("p", recursive=False)
                if paragraph:
                    text = clean_text(paragraph.get_text(" "))
                    if text:
                        description = text
                        break

    return {"title": heading, "description": description}


def extract_hero_content(tag: Tag) -> dict[str, Any]:
    paragraphs = [clean_text(paragraph.get_text(" ")) for paragraph in tag.find_all("p")]
    buttons = extract_buttons(tag)
    images = extract_images(tag)

    return {
        "eyebrow": paragraphs[0] if paragraphs else "",
        "description": paragraphs[1] if len(paragraphs) > 1 else "",
        "primaryCta": buttons[0] if buttons else None,
        "secondaryCta": buttons[1] if len(buttons) > 1 else None,
        "image": images[0] if images else None,
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


def extract_pricing_items(tag: Tag) -> list[dict[str, Any]]:
    items = []
    for card in find_repeated_elements(tag, "pricing-card"):
        paragraphs = [clean_text(paragraph.get_text(" ")) for paragraph in card.find_all("p")]
        price = next((text for text in paragraphs if "$" in text or text.lower() == "custom"), "")
        description = next((text for text in paragraphs if text != price), "")

        items.append(
            {
                "title": extract_main_heading(card)["text"],
                "price": price,
                "description": description,
                "features": [clean_text(item.get_text(" ")) for item in card.find_all("li")],
                "isHighlighted": "highlighted" in [cls.lower() for cls in get_classes(card)],
            }
        )
    return items


def extract_faq_items(tag: Tag) -> list[dict[str, str]]:
    items = []
    for item in find_repeated_elements(tag, "faq-item"):
        question = extract_main_heading(item)["text"]
        answer_tag = item.find("p")
        items.append(
            {
                "question": question,
                "answer": clean_text(answer_tag.get_text(" ")) if answer_tag else "",
            }
        )

    if items:
        return items

    for details in tag.find_all("details"):
        summary = details.find("summary")
        items.append(
            {
                "question": clean_text(summary.get_text(" ")) if summary else "",
                "answer": clean_text(details.get_text(" ")),
            }
        )
    return items


def extract_testimonial_items(tag: Tag) -> list[dict[str, str]]:
    items = []
    for card in find_repeated_elements(tag, "testimonial-card"):
        quote = card.find("blockquote")
        author = card.find(class_="author")
        role = card.find(class_="role")
        items.append(
            {
                "quote": clean_text(quote.get_text(" ")) if quote else "",
                "authorName": clean_text(author.get_text(" ")) if author else "",
                "authorRole": clean_text(role.get_text(" ")) if role else "",
            }
        )
    return items


def extract_card_items(tag: Tag) -> list[dict[str, Any]]:
    items = []
    for card in find_repeated_elements(tag, "feature-card"):
        description = card.find("p")
        image = card.find("img")
        buttons = extract_buttons(card)
        items.append(
            {
                "title": extract_main_heading(card)["text"],
                "description": clean_text(description.get_text(" ")) if description else "",
                "image": extract_images(card)[0] if image else None,
                "cta": buttons[0] if buttons else None,
            }
        )
    return items


def extract_form_details(tag: Tag) -> dict[str, Any] | None:
    form = tag.find("form")
    if not form:
        return None

    submit = form.find(["button", "input"], attrs={"type": "submit"}) or form.find("button")
    fields = []
    for field in form.find_all(FORM_FIELD_TAGS):
        fields.append(
            {
                "label": find_field_label(form, field),
                "name": clean_text(field.get("name") or field.get("id")),
                "type": clean_text(field.get("type") or field.name),
                "required": field.has_attr("required"),
            }
        )

    return {
        "action": clean_text(form.get("action")),
        "method": clean_text(form.get("method") or "get").lower(),
        "fields": fields,
        "submitLabel": clean_text(submit.get_text(" ") or submit.get("value")) if submit else "",
    }


def find_field_label(form: Tag, field: Tag) -> str:
    field_id = field.get("id")
    if field_id:
        label = form.find("label", attrs={"for": field_id})
        if label:
            return clean_text(label.get_text(" "))

    parent_label = field.find_parent("label")
    return clean_text(parent_label.get_text(" ")) if parent_label else ""


def find_repeated_elements(tag: Tag, class_name: str) -> list[Tag]:
    return tag.find_all(class_=lambda value: has_class(value, class_name))


def has_class(value: Any, class_name: str) -> bool:
    if not value:
        return False
    if isinstance(value, str):
        return class_name in value.split()
    return class_name in value


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
                "fieldsDetected": infer_repeated_group_fields(sample, class_name),
                "sampleItems": [
                    extract_repeated_item_sample(item, class_name)
                    for item in elements_by_class[class_name][:3]
                ],
                "hasHeading": bool(sample.find(["h3", "h4"])),
                "hasDescription": bool(sample.find("p")),
                "hasImage": bool(sample.find("img")),
            }
        )

    return groups


def infer_repeated_group_fields(tag: Tag, class_name: str = "") -> list[str]:
    class_name = class_name.lower()

    if "faq" in class_name:
        return ["question", "answer"]

    if "testimonial" in class_name:
        return ["quote", "authorName", "authorRole"]

    if "pricing" in class_name:
        fields = ["title", "price", "description", "features"]
        if "highlighted" in [cls.lower() for cls in get_classes(tag)]:
            fields.append("isHighlighted")
        else:
            fields.append("isHighlighted")
        return fields

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


def extract_repeated_item_sample(tag: Tag, class_name: str) -> dict[str, Any]:
    class_name = class_name.lower()

    if "pricing" in class_name:
        return extract_pricing_item(tag)
    if "faq" in class_name:
        return extract_faq_item(tag)
    if "testimonial" in class_name:
        return extract_testimonial_item(tag)

    return extract_generic_card_item(tag)


def extract_pricing_item(card: Tag) -> dict[str, Any]:
    paragraphs = [clean_text(paragraph.get_text(" ")) for paragraph in card.find_all("p")]
    price = next((text for text in paragraphs if "$" in text or text.lower() == "custom"), "")
    description = next((text for text in paragraphs if text != price), "")

    return {
        "title": extract_main_heading(card)["text"],
        "price": price,
        "description": description,
        "features": [clean_text(item.get_text(" ")) for item in card.find_all("li")],
        "isHighlighted": "highlighted" in [cls.lower() for cls in get_classes(card)],
    }


def extract_faq_item(item: Tag) -> dict[str, str]:
    answer = item.find("p")
    return {
        "question": extract_main_heading(item)["text"],
        "answer": clean_text(answer.get_text(" ")) if answer else "",
    }


def extract_testimonial_item(card: Tag) -> dict[str, str]:
    quote = card.find("blockquote")
    author = card.find(class_="author")
    role = card.find(class_="role")
    return {
        "quote": clean_text(quote.get_text(" ")) if quote else "",
        "authorName": clean_text(author.get_text(" ")) if author else "",
        "authorRole": clean_text(role.get_text(" ")) if role else "",
    }


def extract_generic_card_item(card: Tag) -> dict[str, Any]:
    description = card.find("p")
    buttons = extract_buttons(card)
    images = extract_images(card)

    return {
        "title": extract_main_heading(card)["text"],
        "description": clean_text(description.get_text(" ")) if description else "",
        "image": images[0] if images else None,
        "cta": buttons[0] if buttons else None,
    }


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
