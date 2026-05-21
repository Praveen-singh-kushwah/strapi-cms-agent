"""Generate Strapi v5 schema files from a validated CMS plan."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.schema_models import CmsPlan, ComponentPlan, FieldPlan, SingleTypeAttribute


AI_AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = AI_AGENT_ROOT / "generated" / "strapi"
SUPPORTED_STRAPI_FIELD_TYPES = {
    "string",
    "text",
    "richtext",
    "boolean",
    "integer",
    "decimal",
    "email",
    "json",
    "media",
    "component",
    "dynamiczone",
}


def build_strapi_schema_files(
    cms_plan: CmsPlan | dict[str, Any],
    *,
    draft_and_publish: bool = True,
) -> list[dict[str, Any]]:
    """Build Strapi schema file payloads in memory without writing files."""
    plan = coerce_cms_plan(cms_plan)
    components = [*plan.components, *missing_shared_components(plan)]
    files = [
        {
            "kind": "contentType",
            "uid": plan.pageModel.apiName,
            "path": content_type_schema_path(plan),
            "content": build_content_type_schema(plan, draft_and_publish=draft_and_publish),
        }
    ]

    for component in components:
        files.append(
            {
                "kind": "component",
                "uid": component.uid,
                "path": component_schema_path(component),
                "content": build_component_schema(component),
            }
        )

    return files


def missing_shared_components(cms_plan: CmsPlan) -> list[ComponentPlan]:
    """Build shared component schemas when the plan references known shared UIDs."""
    existing_uids = {component.uid for component in cms_plan.components}
    missing_uids = sorted(
        uid
        for uid in referenced_component_uids(cms_plan)
        if uid.startswith("shared.") and uid not in existing_uids
    )

    components = []
    for uid in missing_uids:
        component = build_known_shared_component(uid)
        if component is not None:
            components.append(component)
    return components


def referenced_component_uids(cms_plan: CmsPlan) -> set[str]:
    references = {
        attribute.component
        for attribute in cms_plan.singleTypeAttributes
        if isinstance(attribute.component, str)
    }
    references.update(
        field.component
        for component in cms_plan.components
        for field in component.fields
        if isinstance(field.component, str)
    )
    return {reference for reference in references if reference}


def build_known_shared_component(uid: str) -> ComponentPlan | None:
    if uid == "shared.seo":
        return ComponentPlan(
            uid="shared.seo",
            category="shared",
            displayName="SEO",
            fileName="seo",
            fields=[
                FieldPlan(name="meta_title", type="string"),
                FieldPlan(name="meta_description", type="text"),
            ],
        )
    if uid == "shared.link":
        return ComponentPlan(
            uid="shared.link",
            category="shared",
            displayName="Link",
            fileName="link",
            fields=[
                FieldPlan(name="text", type="string", required=True),
                FieldPlan(name="url", type="string", required=True),
            ],
        )
    if uid == "shared.text-item":
        return ComponentPlan(
            uid="shared.text-item",
            category="shared",
            displayName="Text Item",
            fileName="text-item",
            fields=[
                FieldPlan(name="text", type="string", required=True),
            ],
        )
    return None


def write_strapi_schema_files(
    cms_plan: CmsPlan | dict[str, Any],
    output_dir: str | Path | None = None,
    *,
    draft_and_publish: bool = True,
) -> dict[str, Any]:
    """Write Strapi schema files to a safe output directory."""
    root = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    files = build_strapi_schema_files(cms_plan, draft_and_publish=draft_and_publish)

    written_files = []
    for schema_file in files:
        relative_path = Path(schema_file["path"])
        target_path = root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(schema_file["content"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written_files.append(
            {
                "kind": schema_file["kind"],
                "uid": schema_file["uid"],
                "path": normalize_path(relative_path),
            }
        )

    return {
        "outputDir": str(root.resolve()),
        "fileCount": len(written_files),
        "files": written_files,
    }


def validate_generated_schema_files(output_dir: str | Path | None = None) -> dict[str, Any]:
    """Validate generated Strapi schema JSON files with local guardrails."""
    root = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists():
        return {
            "isValid": False,
            "errors": [f"Output directory does not exist: {root}"],
            "warnings": warnings,
            "summary": {"outputDir": str(root.resolve()), "fileCount": 0, "files": []},
        }

    json_files = sorted(root.rglob("*.json"))
    if not json_files:
        errors.append(f"No generated schema JSON files found in: {root}")

    relative_files = []
    generated_component_uids = generated_component_uids_from_paths(root, json_files)
    referenced_components: set[str] = set()
    for file_path in json_files:
        relative_path = normalize_path(file_path.relative_to(root))
        relative_files.append(relative_path)
        try:
            document = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{relative_path}: invalid JSON: {exc}")
            continue

        errors.extend(validate_schema_document(relative_path, document))
        referenced_components.update(component_references_in_document(document))

    missing_component_files = sorted(referenced_components - generated_component_uids)
    for uid in missing_component_files:
        errors.append(f"{uid}: referenced component schema file was not generated")

    return {
        "isValid": not errors,
        "errors": dedupe_messages(errors),
        "warnings": dedupe_messages(warnings),
        "summary": {
            "outputDir": str(root.resolve()),
            "fileCount": len(json_files),
            "files": relative_files,
        },
    }


def build_content_type_schema(
    cms_plan: CmsPlan | dict[str, Any],
    *,
    draft_and_publish: bool = True,
) -> dict[str, Any]:
    plan = coerce_cms_plan(cms_plan)
    page_model = plan.pageModel

    return {
        "kind": page_model.kind,
        "collectionName": to_snake_case(page_model.pluralName),
        "info": {
            "singularName": page_model.singularName,
            "pluralName": page_model.pluralName,
            "displayName": page_model.displayName,
            "description": page_model.description,
        },
        "options": {
            "draftAndPublish": draft_and_publish,
        },
        "pluginOptions": {},
        "attributes": attributes_from_single_type_attributes(plan.singleTypeAttributes),
    }


def build_component_schema(component: ComponentPlan | dict[str, Any]) -> dict[str, Any]:
    component_plan = component if isinstance(component, ComponentPlan) else ComponentPlan.model_validate(component)
    return {
        "collectionName": component_collection_name(component_plan),
        "info": {
            "displayName": component_plan.displayName,
        },
        "pluginOptions": {},
        "attributes": attributes_from_fields(component_plan.fields),
    }


def attributes_from_fields(fields: list[FieldPlan]) -> dict[str, Any]:
    return {field.name: field_to_strapi_attribute(field) for field in fields}


def attributes_from_single_type_attributes(attributes: list[SingleTypeAttribute]) -> dict[str, Any]:
    return {attribute.name: single_type_attribute_to_strapi_attribute(attribute) for attribute in attributes}


def field_to_strapi_attribute(field: FieldPlan) -> dict[str, Any]:
    if field.type == "dynamiczone":
        raise ValueError(f"{field.name}: dynamiczone fields are not supported by the MVP generator yet")

    attribute: dict[str, Any] = {"type": field.type}
    if field.required:
        attribute["required"] = True

    if field.type == "component":
        attribute["component"] = field.component
        attribute["repeatable"] = bool(field.repeatable)
    elif field.type == "media":
        attribute["multiple"] = bool(field.multiple)
        if field.allowedTypes:
            attribute["allowedTypes"] = field.allowedTypes

    return attribute


def single_type_attribute_to_strapi_attribute(attribute: SingleTypeAttribute) -> dict[str, Any]:
    if attribute.type == "dynamiczone":
        raise ValueError(f"{attribute.name}: dynamiczone attributes are not supported by the MVP generator yet")

    result: dict[str, Any] = {"type": attribute.type}
    if attribute.type == "component":
        result["component"] = attribute.component
        result["repeatable"] = bool(attribute.repeatable)
    return result


def content_type_schema_path(cms_plan: CmsPlan) -> str:
    api_name = cms_plan.pageModel.apiName
    singular_name = cms_plan.pageModel.singularName
    return normalize_path(Path("src") / "api" / api_name / "content-types" / singular_name / "schema.json")


def component_schema_path(component: ComponentPlan) -> str:
    return normalize_path(Path("src") / "components" / component.category / f"{component.fileName}.json")


def component_collection_name(component: ComponentPlan) -> str:
    return f"components_{to_snake_case(component.category)}_{to_snake_case(component.fileName)}"


def coerce_cms_plan(cms_plan: CmsPlan | dict[str, Any]) -> CmsPlan:
    return cms_plan if isinstance(cms_plan, CmsPlan) else CmsPlan.model_validate(cms_plan)


def validate_schema_document(relative_path: str, document: Any) -> list[str]:
    errors = []
    if not isinstance(document, dict):
        return [f"{relative_path}: schema file must contain a JSON object"]

    forbidden_keys = {"seedData", "warnings"}
    for key in forbidden_keys.intersection(document):
        errors.append(f"{relative_path}: schema file must not include {key}")

    if relative_path.startswith("src/components/"):
        errors.extend(validate_component_schema_document(relative_path, document))
    elif relative_path.startswith("src/api/"):
        errors.extend(validate_content_type_schema_document(relative_path, document))
    else:
        errors.append(f"{relative_path}: generated file is outside expected Strapi schema folders")

    return errors


def generated_component_uids_from_paths(root: Path, json_files: list[Path]) -> set[str]:
    component_uids = set()
    for file_path in json_files:
        try:
            relative_parts = file_path.relative_to(root).parts
        except ValueError:
            continue
        if len(relative_parts) != 4:
            continue
        if relative_parts[:2] != ("src", "components"):
            continue
        category = relative_parts[2]
        file_name = Path(relative_parts[3]).stem
        component_uids.add(f"{category}.{file_name}")
    return component_uids


def component_references_in_document(document: Any) -> set[str]:
    if not isinstance(document, dict):
        return set()
    references = set()
    attributes = document.get("attributes")
    if not isinstance(attributes, dict):
        return references
    for attribute in attributes.values():
        if isinstance(attribute, dict) and attribute.get("type") == "component":
            component = attribute.get("component")
            if isinstance(component, str) and component:
                references.add(component)
    return references


def validate_component_schema_document(relative_path: str, document: dict[str, Any]) -> list[str]:
    errors = validate_common_schema_keys(relative_path, document, required_keys={"collectionName", "info", "pluginOptions", "attributes"})
    info = document.get("info")
    if not isinstance(info, dict) or not isinstance(info.get("displayName"), str):
        errors.append(f"{relative_path}: component info.displayName must be set")
    errors.extend(validate_attributes_document(relative_path, document.get("attributes")))
    return errors


def validate_content_type_schema_document(relative_path: str, document: dict[str, Any]) -> list[str]:
    errors = validate_common_schema_keys(
        relative_path,
        document,
        required_keys={"kind", "collectionName", "info", "options", "pluginOptions", "attributes"},
    )
    if document.get("kind") != "singleType":
        errors.append(f"{relative_path}: content type kind must be singleType")

    info = document.get("info")
    if not isinstance(info, dict):
        errors.append(f"{relative_path}: info must be an object")
    else:
        for key in ("singularName", "pluralName", "displayName"):
            if not isinstance(info.get(key), str) or not info[key]:
                errors.append(f"{relative_path}: info.{key} must be set")

    options = document.get("options")
    if not isinstance(options, dict) or not isinstance(options.get("draftAndPublish"), bool):
        errors.append(f"{relative_path}: options.draftAndPublish must be true or false")

    errors.extend(validate_attributes_document(relative_path, document.get("attributes")))
    return errors


def validate_common_schema_keys(relative_path: str, document: dict[str, Any], required_keys: set[str]) -> list[str]:
    errors = []
    missing_keys = sorted(required_keys - set(document))
    for key in missing_keys:
        errors.append(f"{relative_path}: missing required key {key}")

    if not isinstance(document.get("collectionName"), str) or not document.get("collectionName"):
        errors.append(f"{relative_path}: collectionName must be set")
    if not isinstance(document.get("pluginOptions"), dict):
        errors.append(f"{relative_path}: pluginOptions must be an object")
    if not isinstance(document.get("attributes"), dict):
        errors.append(f"{relative_path}: attributes must be an object")

    return errors


def validate_attributes_document(relative_path: str, attributes: Any) -> list[str]:
    if not isinstance(attributes, dict):
        return []

    errors = []
    for name, attribute in attributes.items():
        location = f"{relative_path}: attributes.{name}"
        if not isinstance(attribute, dict):
            errors.append(f"{location} must be an object")
            continue

        attribute_type = attribute.get("type")
        if attribute_type not in SUPPORTED_STRAPI_FIELD_TYPES:
            errors.append(f"{location}.type is unsupported or missing")

        if attribute_type == "component":
            if not isinstance(attribute.get("component"), str) or not attribute["component"]:
                errors.append(f"{location}.component must be set")
            if not isinstance(attribute.get("repeatable"), bool):
                errors.append(f"{location}.repeatable must be true or false")

        if attribute_type == "media":
            if not isinstance(attribute.get("multiple"), bool):
                errors.append(f"{location}.multiple must be true or false")
            if "allowedTypes" in attribute and not isinstance(attribute["allowedTypes"], list):
                errors.append(f"{location}.allowedTypes must be a list")

        if attribute_type == "dynamiczone":
            errors.append(f"{location}: dynamiczone is not supported by the MVP generator yet")

        if "required" in attribute and not isinstance(attribute["required"], bool):
            errors.append(f"{location}.required must be true or false")
        if "sourceSectionIndex" in attribute:
            errors.append(f"{location}: sourceSectionIndex must not be written to Strapi schema")

    return errors


def to_snake_case(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return result.strip("_").lower()


def normalize_path(path: str | Path) -> str:
    return Path(path).as_posix()


def dedupe_messages(messages: list[str]) -> list[str]:
    seen = set()
    result = []
    for message in messages:
        if message not in seen:
            seen.add(message)
            result.append(message)
    return result
