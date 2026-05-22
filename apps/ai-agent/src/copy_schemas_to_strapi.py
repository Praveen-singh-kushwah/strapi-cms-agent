"""Copy generated Strapi schema files into a local Strapi project."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from src.strapi_schema_generator import DEFAULT_OUTPUT_DIR, normalize_path, validate_generated_schema_files


SCHEMA_SUBDIRS = ("api", "components")


def copy_generated_schemas_to_strapi(
    target_dir: str | Path,
    *,
    source_dir: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy generated schema JSON files into a Strapi app's src folder."""
    source_root = Path(source_dir).resolve() if source_dir is not None else DEFAULT_OUTPUT_DIR.resolve()
    target_root = Path(target_dir).resolve()
    report: dict[str, Any] = {
        "isValid": False,
        "dryRun": dry_run,
        "sourceDir": str(source_root),
        "targetDir": str(target_root),
        "sourceValidation": None,
        "fileCount": 0,
        "files": [],
        "errors": [],
        "warnings": [],
    }

    errors: list[str] = []
    warnings: list[str] = []

    source_validation = validate_source_schema_dir(source_root)
    report["sourceValidation"] = source_validation
    errors.extend(source_validation["errors"])
    warnings.extend(source_validation["warnings"])

    target_validation = validate_strapi_target(target_root)
    errors.extend(target_validation["errors"])
    warnings.extend(target_validation["warnings"])

    if errors:
        report["errors"] = dedupe_messages(errors)
        report["warnings"] = dedupe_messages(warnings)
        return report

    planned_files = plan_schema_file_copies(source_root, target_root)
    if not planned_files:
        report["errors"] = [f"No schema JSON files found under {source_root / 'src'}"]
        report["warnings"] = dedupe_messages(warnings)
        return report

    skipped_files = non_json_files_under_schema_dirs(source_root)
    if skipped_files:
        warnings.append("Skipped non-JSON files: " + ", ".join(skipped_files))

    if not dry_run:
        for item in planned_files:
            target_path = Path(item["absoluteTargetPath"])
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["absoluteSourcePath"], target_path)

    report["isValid"] = True
    report["fileCount"] = len(planned_files)
    report["files"] = [
        {
            "source": item["source"],
            "target": item["target"],
            "action": item["action"],
        }
        for item in planned_files
    ]
    report["errors"] = []
    report["warnings"] = dedupe_messages(warnings)
    return report


def validate_source_schema_dir(source_root: Path) -> dict[str, Any]:
    """Validate the generated schema output before copying it into Strapi."""
    validation = validate_generated_schema_files(source_root)
    errors = list(validation["errors"])
    warnings = list(validation["warnings"])

    source_src = source_root / "src"
    if not source_src.exists():
        errors.append(f"Generated source directory does not exist: {source_src}")

    for subdir in SCHEMA_SUBDIRS:
        subdir_path = source_src / subdir
        if not subdir_path.exists():
            errors.append(f"Generated schema directory does not exist: {subdir_path}")

    return {
        "isValid": not errors,
        "errors": dedupe_messages(errors),
        "warnings": dedupe_messages(warnings),
        "summary": validation.get("summary", {}),
    }


def validate_strapi_target(target_root: Path) -> dict[str, Any]:
    """Validate that the copy destination looks like a local Strapi app."""
    errors: list[str] = []
    warnings: list[str] = []

    if not target_root.exists():
        errors.append(f"Target Strapi directory does not exist: {target_root}")
        return {"isValid": False, "errors": errors, "warnings": warnings}

    if not target_root.is_dir():
        errors.append(f"Target Strapi path is not a directory: {target_root}")
        return {"isValid": False, "errors": errors, "warnings": warnings}

    package_json_path = target_root / "package.json"
    src_path = target_root / "src"
    if not package_json_path.exists():
        errors.append(f"Target does not contain package.json: {package_json_path}")
    else:
        errors.extend(validate_strapi_package_json(package_json_path))

    if not src_path.exists():
        errors.append(f"Target does not contain a src directory: {src_path}")

    for subdir in SCHEMA_SUBDIRS:
        target_subdir = src_path / subdir
        if not target_subdir.exists():
            warnings.append(f"Target schema directory will be created if needed: {target_subdir}")

    return {
        "isValid": not errors,
        "errors": dedupe_messages(errors),
        "warnings": dedupe_messages(warnings),
    }


def validate_strapi_package_json(package_json_path: Path) -> list[str]:
    try:
        package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{package_json_path}: invalid JSON: {exc}"]

    dependencies = package_data.get("dependencies")
    dev_dependencies = package_data.get("devDependencies")
    combined_dependencies = {}
    if isinstance(dependencies, dict):
        combined_dependencies.update(dependencies)
    if isinstance(dev_dependencies, dict):
        combined_dependencies.update(dev_dependencies)

    if "@strapi/strapi" not in combined_dependencies:
        return [f"{package_json_path}: @strapi/strapi dependency was not found"]

    return []


def plan_schema_file_copies(source_root: Path, target_root: Path) -> list[dict[str, str]]:
    source_src = source_root / "src"
    target_src = target_root / "src"
    planned_files: list[dict[str, str]] = []

    for subdir in SCHEMA_SUBDIRS:
        for source_path in sorted((source_src / subdir).rglob("*.json")):
            relative_path = source_path.relative_to(source_src)
            target_path = target_src / relative_path
            planned_files.append(
                {
                    "source": normalize_path(Path("src") / relative_path),
                    "target": normalize_path(Path("src") / relative_path),
                    "absoluteSourcePath": str(source_path),
                    "absoluteTargetPath": str(target_path),
                    "action": "overwrite" if target_path.exists() else "create",
                }
            )

    return planned_files


def non_json_files_under_schema_dirs(source_root: Path) -> list[str]:
    source_src = source_root / "src"
    skipped_files: list[str] = []
    for subdir in SCHEMA_SUBDIRS:
        root = source_src / subdir
        if not root.exists():
            continue
        for source_path in sorted(path for path in root.rglob("*") if path.is_file()):
            if source_path.suffix.lower() != ".json":
                skipped_files.append(normalize_path(Path("src") / source_path.relative_to(source_src)))
    return skipped_files


def dedupe_messages(messages: list[str]) -> list[str]:
    seen = set()
    result = []
    for message in messages:
        if message and message not in seen:
            seen.add(message)
            result.append(message)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy generated Strapi schema JSON files into a local Strapi project.",
    )
    parser.add_argument(
        "target_dir",
        help="Path to the target Strapi app directory.",
    )
    parser.add_argument(
        "--source-dir",
        help="Generated Strapi output directory. Defaults to generated/strapi.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report planned copies without writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    report = copy_generated_schemas_to_strapi(
        args.target_dir,
        source_dir=args.source_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["isValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
