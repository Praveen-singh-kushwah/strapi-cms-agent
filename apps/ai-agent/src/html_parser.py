"""Reusable HTML parsing helpers for the notebook MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


NOISE_TAGS = ("script", "style", "noscript", "svg", "meta", "link")
UNWANTED_TAGS = NOISE_TAGS
SECTION_TAGS = ("header", "nav", "main", "section", "article", "footer")


def load_html_from_file(file_path: str | Path) -> str:
    """Load an HTML file as UTF-8 text."""
    return Path(file_path).read_text(encoding="utf-8")


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML with BeautifulSoup and remove non-content noise tags."""
    soup = BeautifulSoup(html, "lxml")
    remove_unwanted_tags(soup)
    return soup


def remove_unwanted_tags(soup: BeautifulSoup) -> None:
    """Remove tags that should not affect content structure analysis."""
    for tag in soup.find_all(UNWANTED_TAGS):
        tag.decompose()


def find_page_root(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    """Prefer the visible page root that contains meaningful content."""
    return soup.find("main") or soup.body or soup


def clean_text(value: str | None) -> str:
    """Normalize whitespace for extracted text fields."""
    if not value:
        return ""
    return " ".join(value.split())


def get_classes(tag: Tag) -> list[str]:
    """Return classes from a tag as a predictable list of strings."""
    classes = tag.get("class", [])
    if isinstance(classes, str):
        return [classes]
    return list(classes)


def extract_page_title(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    return clean_text(title.get_text()) if title else ""


def extract_headings(soup: BeautifulSoup) -> list[dict[str, str]]:
    headings: list[dict[str, str]] = []
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = clean_text(heading.get_text())
        if text:
            headings.append({"level": heading.name, "text": text})
    return headings


def extract_links(soup: BeautifulSoup) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for link in soup.find_all("a"):
        href = clean_text(link.get("href"))
        text = clean_text(link.get_text())
        if href or text:
            links.append({"text": text, "href": href})
    return links


def extract_buttons(soup: BeautifulSoup | Tag) -> list[dict[str, str]]:
    buttons: list[dict[str, str]] = []
    for button in soup.find_all(["a", "button"]):
        text = clean_text(button.get_text(" "))
        href = clean_text(button.get("href"))
        if text:
            buttons.append({"text": text, "href": href})
    return buttons


def extract_images(soup: BeautifulSoup) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for image in soup.find_all("img"):
        src = clean_text(image.get("src"))
        alt = clean_text(image.get("alt"))
        if src or alt:
            images.append({"src": src, "alt": alt})
    return images


def extract_forms(soup: BeautifulSoup) -> list[dict[str, Any]]:
    forms: list[dict[str, Any]] = []
    for form in soup.find_all("form"):
        fields = []
        for field in form.find_all(["input", "textarea", "select"]):
            field_name = clean_text(field.get("name") or field.get("id"))
            field_type = clean_text(field.get("type") or field.name)
            label = find_label_text(form, field)
            fields.append(
                {
                    "tag": field.name,
                    "name": field_name,
                    "type": field_type,
                    "label": label,
                    "required": field.has_attr("required"),
                }
            )

        forms.append(
            {
                "action": clean_text(form.get("action")),
                "method": clean_text(form.get("method") or "get").lower(),
                "classes": get_classes(form),
                "fields": fields,
            }
        )
    return forms


def find_label_text(form: Tag, field: Tag) -> str:
    field_id = field.get("id")
    if field_id:
        label = form.find("label", attrs={"for": field_id})
        if label:
            return clean_text(label.get_text())

    parent_label = field.find_parent("label")
    return clean_text(parent_label.get_text()) if parent_label else ""


def extract_sections(soup: BeautifulSoup) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for tag in soup.find_all(SECTION_TAGS):
        title_tag = tag.find(["h1", "h2", "h3"])
        text = clean_text(tag.get_text(" "))
        sections.append(
            {
                "tag": tag.name,
                "id": clean_text(tag.get("id")),
                "classes": get_classes(tag),
                "title": clean_text(title_tag.get_text()) if title_tag else "",
                "text_preview": text[:240],
            }
        )
    return sections


def build_dom_summary(file_path: str | Path) -> dict[str, Any]:
    """Parse an HTML file and return a clean summary for downstream analysis."""
    html = load_html_from_file(file_path)
    soup = parse_html(html)

    return {
        "file_path": str(file_path),
        "title": extract_page_title(soup),
        "root_tag": getattr(find_page_root(soup), "name", "document"),
        "headings": extract_headings(soup),
        "links": extract_links(soup),
        "images": extract_images(soup),
        "forms": extract_forms(soup),
        "sections": extract_sections(soup),
    }
