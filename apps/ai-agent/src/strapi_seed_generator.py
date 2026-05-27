"""Generate Strapi seed payloads from a validated CMS plan."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.schema_models import CmsPlan, ComponentPlan, FieldPlan, SingleTypeAttribute
from src.strapi_schema_generator import missing_shared_components


AI_AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED_OUTPUT_DIR = AI_AGENT_ROOT / "generated" / "strapi" / "seed"
SUPPORTED_SEED_STATUSES = {"draft", "published"}


def build_strapi_seed_payload(
    cms_plan: CmsPlan | dict[str, Any],
    *,
    status: str = "published",
    html_file: str | Path | None = None,
) -> dict[str, Any]:
    """Build an importable Strapi seed payload from the CMS plan seedData."""
    plan = coerce_cms_plan(cms_plan)
    if status not in SUPPORTED_SEED_STATUSES:
        raise ValueError(f"Unsupported seed status: {status}")

    seed_dict = plan.seedData.model_dump(exclude_none=True)
    component_index = {
        component.uid: component
        for component in [*plan.components, *missing_shared_components(plan)]
    }
    media_assets: list[dict[str, Any]] = []
    warnings: list[str] = []
    data: dict[str, Any] = {}

    for attribute in plan.singleTypeAttributes:
        if attribute.name not in seed_dict:
            warnings.append(f"{attribute.name}: no seedData value was provided")
            continue

        data[attribute.name] = transform_seed_value(
            seed_dict[attribute.name],
            attribute,
            component_index,
            path=attribute.name,
            media_assets=media_assets,
            warnings=warnings,
        )

    media_plan = build_media_plan(media_assets, html_file=html_file)

    return {
        "uid": f"api::{plan.pageModel.apiName}.{plan.pageModel.singularName}",
        "apiName": plan.pageModel.apiName,
        "contentTypeName": plan.pageModel.singularName,
        "status": status,
        "data": data,
        "mediaAssets": media_assets,
        "mediaPlan": media_plan,
        "warnings": dedupe_messages([*plan.warnings, *warnings]),
    }


def transform_seed_value(
    value: Any,
    field: FieldPlan | SingleTypeAttribute,
    component_index: dict[str, ComponentPlan],
    *,
    path: str,
    media_assets: list[dict[str, Any]],
    warnings: list[str],
) -> Any:
    """Transform one seed value according to its planned Strapi field type."""
    if field.type == "media":
        if value:
            media_assets.append(media_asset_from_value(path, value))
        return None

    if field.type == "component":
        if not field.component:
            warnings.append(f"{path}: component field is missing a component uid")
            return [] if field.repeatable else None

        component = component_index.get(field.component)
        if component is None:
            warnings.append(f"{path}: unknown component uid {field.component}")
            return [] if field.repeatable else None

        if field.repeatable:
            if value is None:
                return []
            if not isinstance(value, list):
                warnings.append(f"{path}: expected a list for repeatable component seed data")
                return []
            return [
                transform_component_seed(
                    item,
                    component,
                    component_index,
                    path=f"{path}[{index}]",
                    media_assets=media_assets,
                    warnings=warnings,
                )
                for index, item in enumerate(value)
            ]

        if value is None:
            return None
        return transform_component_seed(
            value,
            component,
            component_index,
            path=path,
            media_assets=media_assets,
            warnings=warnings,
        )

    if field.type == "boolean":
        return bool(value)

    return value


def transform_component_seed(
    value: Any,
    component: ComponentPlan,
    component_index: dict[str, ComponentPlan],
    *,
    path: str,
    media_assets: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    """Transform a component seed object and drop fields not present in its schema."""
    if not isinstance(value, dict):
        warnings.append(f"{path}: expected component seed data to be an object")
        return {}

    result: dict[str, Any] = {}
    field_by_name = {field.name: field for field in component.fields}
    extra_fields = sorted(
        field_name
        for field_name in set(value) - set(field_by_name)
        if not is_empty_optional_extra_value(value[field_name])
    )
    if extra_fields:
        warnings.append(f"{path}: dropped fields not present in {component.uid}: {', '.join(extra_fields)}")

    for field in component.fields:
        if field.name not in value:
            if field.required:
                warnings.append(f"{path}.{field.name}: required field has no seed value")
            continue

        if should_omit_empty_optional_value(field, value[field.name]):
            continue

        result[field.name] = transform_seed_value(
            value[field.name],
            field,
            component_index,
            path=f"{path}.{field.name}",
            media_assets=media_assets,
            warnings=warnings,
        )

    return result


def should_omit_empty_optional_value(field: FieldPlan, value: Any) -> bool:
    if field.required:
        return False
    if value is None:
        return True
    return field.type in {"string", "text", "richtext", "email"} and isinstance(value, str) and not value.strip()


def is_empty_optional_extra_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def media_asset_from_value(path: str, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "fieldPath": path,
            "src": value.get("src", ""),
            "alt": value.get("alt", ""),
        }

    return {
        "fieldPath": path,
        "src": str(value),
        "alt": "",
    }


def build_media_plan(
    media_assets: list[dict[str, Any]],
    *,
    html_file: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Resolve media asset references into local upload candidates."""
    html_path = Path(html_file).resolve() if html_file is not None else None
    html_dir = html_path.parent if html_path is not None else None

    return [
        build_media_plan_item(asset, html_dir=html_dir)
        for asset in media_assets
    ]


def build_media_plan_item(
    asset: dict[str, Any],
    *,
    html_dir: Path | None = None,
) -> dict[str, Any]:
    src = str(asset.get("src") or "")
    resolved_path = resolve_media_source(src, html_dir=html_dir)
    exists = bool(resolved_path and resolved_path.exists())

    return {
        "fieldPath": asset.get("fieldPath", ""),
        "src": src,
        "alt": asset.get("alt", ""),
        "resolvedPath": str(resolved_path) if resolved_path is not None else "",
        "status": "ready" if exists else "missing",
    }


def resolve_media_source(src: str, *, html_dir: Path | None = None) -> Path | None:
    if not src or is_remote_url(src) or src.startswith("data:"):
        return None

    source_path = Path(src)
    if source_path.is_absolute():
        return source_path

    if html_dir is None:
        return source_path

    return (html_dir / source_path).resolve()


def is_remote_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "//"))


def write_strapi_seed_file(
    cms_plan: CmsPlan | dict[str, Any],
    output_dir: str | Path | None = None,
    *,
    status: str = "published",
    html_file: str | Path | None = None,
) -> dict[str, Any]:
    """Write the generated seed payload to disk."""
    plan = coerce_cms_plan(cms_plan)
    root = Path(output_dir) if output_dir is not None else DEFAULT_SEED_OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)

    payload = build_strapi_seed_payload(plan, status=status, html_file=html_file)
    target_path = root / f"{plan.pageModel.apiName}.seed.json"
    target_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    validation = validate_strapi_seed_payload(payload, plan)
    return {
        "outputDir": str(root.resolve()),
        "path": str(target_path.resolve()),
        "validation": validation,
    }


def validate_strapi_seed_payload(
    payload: dict[str, Any],
    cms_plan: CmsPlan | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the seed payload shape before handing it to Strapi."""
    errors: list[str] = []
    warnings: list[str] = []

    uid = payload.get("uid")
    if not isinstance(uid, str) or not re.fullmatch(r"api::[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*", uid):
        errors.append("uid must look like api::api-name.content-type-name")

    if payload.get("status") not in SUPPORTED_SEED_STATUSES:
        errors.append("status must be draft or published")

    data = payload.get("data")
    if not isinstance(data, dict) or not data:
        errors.append("data must be a non-empty object")

    media_assets = payload.get("mediaAssets")
    if not isinstance(media_assets, list):
        errors.append("mediaAssets must be a list")

    media_plan = payload.get("mediaPlan")
    if not isinstance(media_plan, list):
        errors.append("mediaPlan must be a list")

    if cms_plan is not None and isinstance(data, dict):
        plan = coerce_cms_plan(cms_plan)
        expected_keys = {attribute.name for attribute in plan.singleTypeAttributes}
        actual_keys = set(data)
        missing_keys = sorted(expected_keys - actual_keys)
        extra_keys = sorted(actual_keys - expected_keys)
        for key in missing_keys:
            errors.append(f"data.{key}: missing single type seed value")
        for key in extra_keys:
            errors.append(f"data.{key}: not present in singleTypeAttributes")

    if isinstance(media_assets, list) and media_assets:
        warnings.append("mediaAssets are recorded; ready files are uploaded by the sandbox seed importer")

    if isinstance(media_plan, list):
        missing_media = [
            item.get("fieldPath", "")
            for item in media_plan
            if isinstance(item, dict) and item.get("status") == "missing"
        ]
        if missing_media:
            warnings.append("missing media files: " + ", ".join(missing_media))

    return {
        "isValid": not errors,
        "errors": dedupe_messages(errors),
        "warnings": dedupe_messages(warnings),
        "summary": {
            "uid": uid,
            "status": payload.get("status"),
            "dataKeys": sorted(data.keys()) if isinstance(data, dict) else [],
            "mediaAssetCount": len(media_assets) if isinstance(media_assets, list) else 0,
            "mediaPlanReadyCount": count_media_plan_status(media_plan, "ready") if isinstance(media_plan, list) else 0,
            "mediaPlanMissingCount": count_media_plan_status(media_plan, "missing") if isinstance(media_plan, list) else 0,
        },
    }


def coerce_cms_plan(cms_plan: CmsPlan | dict[str, Any]) -> CmsPlan:
    return cms_plan if isinstance(cms_plan, CmsPlan) else CmsPlan.model_validate(cms_plan)


def count_media_plan_status(media_plan: list[Any], status: str) -> int:
    return sum(1 for item in media_plan if isinstance(item, dict) and item.get("status") == status)


def dedupe_messages(messages: list[str]) -> list[str]:
    seen = set()
    result = []
    for message in messages:
        if message and message not in seen:
            seen.add(message)
            result.append(message)
    return result
