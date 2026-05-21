"""Human-readable validation report for generated Strapi CMS plans."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.schema_models import (
    KNOWN_SHARED_COMPONENT_UIDS,
    CmsPlan,
    KEBAB_CASE_PATTERN,
    SNAKE_CASE_PATTERN,
    UID_PATTERN,
)


def validate_cms_plan(plan: CmsPlan | dict[str, Any]) -> dict[str, Any]:
    """Validate a CMS plan and return a notebook-friendly report."""
    errors: list[str] = []
    warnings: list[str] = []
    cms_plan = coerce_cms_plan(plan, errors)

    if cms_plan is None:
        return {
            "isValid": False,
            "errors": errors,
            "warnings": warnings,
            "summary": summarize_raw_plan(plan),
        }

    errors.extend(validate_component_uids(cms_plan))
    errors.extend(validate_component_field_names(cms_plan))
    errors.extend(validate_component_references(cms_plan))
    errors.extend(validate_single_type_attributes(cms_plan))
    errors.extend(validate_seed_data_keys(cms_plan))

    warnings.extend(validate_media_fields(cms_plan))
    warnings.extend(validate_repeatable_scalar_fields(cms_plan))
    warnings.extend(validate_page_model_names(cms_plan))
    warnings.extend(validate_global_blocks(cms_plan))
    warnings.extend(cms_plan.warnings)

    return {
        "isValid": not errors,
        "errors": dedupe_messages(errors),
        "warnings": dedupe_messages(warnings),
        "summary": summarize_cms_plan(cms_plan),
    }


def coerce_cms_plan(plan: CmsPlan | dict[str, Any], errors: list[str]) -> CmsPlan | None:
    if isinstance(plan, CmsPlan):
        return plan

    try:
        return CmsPlan.model_validate(plan)
    except ValidationError as exc:
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()))
            message = error.get("msg", "Invalid value")
            errors.append(f"{location}: {message}" if location else message)
        return None


def validate_component_uids(cms_plan: CmsPlan) -> list[str]:
    errors = []
    seen = set()

    for component in cms_plan.components:
        if not UID_PATTERN.match(component.uid):
            errors.append(f"Component UID is not category.component-name: {component.uid}")
        if component.uid in seen:
            errors.append(f"Duplicate component UID: {component.uid}")
        seen.add(component.uid)
        if not KEBAB_CASE_PATTERN.match(component.category):
            errors.append(f"Component category must be kebab-case: {component.category}")
        if not KEBAB_CASE_PATTERN.match(component.fileName):
            errors.append(f"Component fileName must be kebab-case: {component.fileName}")

    return errors


def validate_component_field_names(cms_plan: CmsPlan) -> list[str]:
    errors = []

    for component in cms_plan.components:
        field_names = set()
        for field in component.fields:
            if not SNAKE_CASE_PATTERN.match(field.name):
                errors.append(f"{component.uid}.{field.name}: field name must be snake_case")
            if field.name in field_names:
                errors.append(f"{component.uid}: duplicate field name '{field.name}'")
            field_names.add(field.name)

    return errors


def validate_component_references(cms_plan: CmsPlan) -> list[str]:
    errors = []
    available_components = {component.uid for component in cms_plan.components} | KNOWN_SHARED_COMPONENT_UIDS

    for component in cms_plan.components:
        for field in component.fields:
            if field.component and field.component not in available_components:
                errors.append(f"{component.uid}.{field.name}: unknown component reference {field.component}")

    return errors


def validate_single_type_attributes(cms_plan: CmsPlan) -> list[str]:
    errors = []
    available_components = {component.uid for component in cms_plan.components} | KNOWN_SHARED_COMPONENT_UIDS
    attribute_names = set()

    for attribute in cms_plan.singleTypeAttributes:
        if not SNAKE_CASE_PATTERN.match(attribute.name):
            errors.append(f"{attribute.name}: single type attribute name must be snake_case")
        if attribute.name in attribute_names:
            errors.append(f"Duplicate single type attribute: {attribute.name}")
        attribute_names.add(attribute.name)

        if attribute.type == "component" and not attribute.component:
            errors.append(f"{attribute.name}: component attribute is missing component uid")
        if attribute.component and attribute.component not in available_components:
            errors.append(f"{attribute.name}: unknown component reference {attribute.component}")

    return errors


def validate_seed_data_keys(cms_plan: CmsPlan) -> list[str]:
    seed_keys = set(cms_plan.seedData.model_dump(exclude_none=True).keys())
    attribute_keys = {attribute.name for attribute in cms_plan.singleTypeAttributes}
    errors = []

    missing_seed_keys = attribute_keys - seed_keys
    unknown_seed_keys = seed_keys - attribute_keys

    for key in sorted(unknown_seed_keys):
        errors.append(f"seedData.{key}: no matching single type attribute")

    for key in sorted(missing_seed_keys):
        errors.append(f"{key}: single type attribute has no seedData entry")

    return errors


def validate_media_fields(cms_plan: CmsPlan) -> list[str]:
    warnings = []

    for component in cms_plan.components:
        for field in component.fields:
            if field.type != "media":
                continue
            if field.multiple is None:
                warnings.append(f"{component.uid}.{field.name}: media field should set multiple true/false")
            if not field.allowedTypes:
                warnings.append(f"{component.uid}.{field.name}: media field should define allowedTypes")

    return warnings


def validate_repeatable_scalar_fields(cms_plan: CmsPlan) -> list[str]:
    warnings = []

    for component in cms_plan.components:
        for field in component.fields:
            if field.repeatable and field.type not in {"component", "dynamiczone"}:
                warnings.append(
                    f"{component.uid}.{field.name}: repeatable scalar fields may need a repeatable component in Strapi"
                )

    return warnings


def validate_page_model_names(cms_plan: CmsPlan) -> list[str]:
    warnings = []
    page_model = cms_plan.pageModel

    if page_model.apiName != page_model.singularName:
        warnings.append("pageModel.apiName and pageModel.singularName differ")
    if not page_model.pluralName.startswith(page_model.singularName):
        warnings.append("pageModel.pluralName does not appear to derive from singularName")

    return warnings


def validate_global_blocks(cms_plan: CmsPlan) -> list[str]:
    warnings = []
    global_blocks = cms_plan.globalBlocks

    for name in ("header", "footer"):
        block = getattr(global_blocks, name)
        if block and block.handling == "global_single_type" and not block.componentPlan:
            warnings.append(f"globalBlocks.{name}: componentPlan is not set")

    return warnings


def summarize_cms_plan(cms_plan: CmsPlan) -> dict[str, Any]:
    seed_data = cms_plan.seedData.model_dump(exclude_none=True)
    component_uids = [component.uid for component in cms_plan.components]
    attribute_names = [attribute.name for attribute in cms_plan.singleTypeAttributes]

    return {
        "pageApiName": cms_plan.pageModel.apiName,
        "componentCount": len(cms_plan.components),
        "singleTypeAttributeCount": len(cms_plan.singleTypeAttributes),
        "seedDataKeyCount": len(seed_data),
        "componentUids": component_uids,
        "singleTypeAttributes": attribute_names,
        "seedDataKeys": list(seed_data.keys()),
    }


def summarize_raw_plan(plan: CmsPlan | dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan, CmsPlan):
        return summarize_cms_plan(plan)
    if not isinstance(plan, dict):
        return {"inputType": type(plan).__name__}

    return {
        "pageApiName": (plan.get("pageModel") or {}).get("apiName"),
        "componentCount": len(plan.get("components") or []),
        "singleTypeAttributeCount": len(plan.get("singleTypeAttributes") or []),
        "seedDataKeyCount": len(plan.get("seedData") or {}),
    }


def dedupe_messages(messages: list[str]) -> list[str]:
    seen = set()
    result = []

    for message in messages:
        if message not in seen:
            seen.add(message)
            result.append(message)

    return result
