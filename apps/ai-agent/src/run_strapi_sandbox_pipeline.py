"""Run the AI-side Strapi sandbox preparation workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.check_schema_snapshot import DEFAULT_SNAPSHOT_PATH, check_schema_snapshot
from src.copy_schemas_to_strapi import copy_generated_schemas_to_strapi
from src.generate_strapi_schemas import generate_strapi_schema_report
from src.generate_strapi_seed import generate_strapi_seed_report


AI_AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SANDBOX_TARGET = AI_AGENT_ROOT.parent / "strapi-sandbox"
DEFAULT_RUN_OUTPUT_ROOT = AI_AGENT_ROOT / "generated" / "strapi" / "runs"


def run_strapi_sandbox_pipeline(
    html_file: str | Path,
    *,
    target_dir: str | Path = DEFAULT_SANDBOX_TARGET,
    schema_output_dir: str | Path | None = None,
    seed_output_dir: str | Path | None = None,
    snapshot_path: str | Path = DEFAULT_SNAPSHOT_PATH,
    use_llm: bool = False,
    use_llm_section_analysis: bool = False,
    skip_snapshot: bool = False,
    dry_run_copy: bool = False,
    status: str = "published",
    draft_and_publish: bool = True,
) -> dict[str, Any]:
    """Run schema generation, snapshot check, schema copy, and seed generation."""
    html_path = Path(html_file)
    target_path = Path(target_dir)
    resolved_schema_output_dir = Path(schema_output_dir) if schema_output_dir else default_schema_output_dir(html_path)
    resolved_seed_output_dir = Path(seed_output_dir) if seed_output_dir else resolved_schema_output_dir / "seed"
    report: dict[str, Any] = {
        "isValid": False,
        "htmlFile": str(html_path),
        "targetDir": str(target_path),
        "usedLLM": use_llm,
        "usedLLMSectionAnalysis": use_llm_section_analysis,
        "schemaOutputDir": str(resolved_schema_output_dir),
        "seedOutputDir": str(resolved_seed_output_dir),
        "seedPath": None,
        "steps": {
            "schemaGeneration": None,
            "snapshotCheck": None,
            "schemaCopy": None,
            "seedGeneration": None,
        },
        "errors": [],
        "nextCommands": build_next_commands(),
    }

    schema_report = generate_strapi_schema_report(
        html_path,
        output_dir=resolved_schema_output_dir,
        use_llm=use_llm,
        use_llm_section_analysis=use_llm_section_analysis,
        draft_and_publish=draft_and_publish,
    )
    report["steps"]["schemaGeneration"] = schema_report
    if not schema_report["isValid"]:
        report["errors"] = prefixed_errors("schemaGeneration", schema_report.get("errors", []))
        return report

    if not skip_snapshot:
        snapshot_report = check_schema_snapshot(
            html_path,
            snapshot_path=snapshot_path,
            output_dir=resolved_schema_output_dir,
            use_llm=use_llm,
            use_llm_section_analysis=use_llm_section_analysis,
            draft_and_publish=draft_and_publish,
        )
        report["steps"]["snapshotCheck"] = snapshot_report
        if not snapshot_report["isValid"]:
            report["errors"] = prefixed_errors("snapshotCheck", snapshot_report.get("errors", []))
            return report
    else:
        report["steps"]["snapshotCheck"] = {
            "isValid": True,
            "skipped": True,
            "errors": [],
        }

    copy_report = copy_generated_schemas_to_strapi(
        target_path,
        source_dir=resolved_schema_output_dir,
        dry_run=dry_run_copy,
    )
    report["steps"]["schemaCopy"] = copy_report
    if not copy_report["isValid"]:
        report["errors"] = prefixed_errors("schemaCopy", copy_report.get("errors", []))
        return report

    seed_report = generate_strapi_seed_report(
        html_path,
        output_dir=resolved_seed_output_dir,
        use_llm=use_llm,
        use_llm_section_analysis=use_llm_section_analysis,
        status=status,
    )
    report["steps"]["seedGeneration"] = seed_report
    if not seed_report["isValid"]:
        report["errors"] = prefixed_errors("seedGeneration", seed_report.get("errors", []))
        return report

    report["isValid"] = True
    report["seedPath"] = seed_report.get("seedWriteReport", {}).get("path")
    report["errors"] = []
    return report


def build_next_commands() -> dict[str, str]:
    return {
        "buildSandbox": (
            '& "$node24\\node.exe" "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js" '
            "run build"
        ),
        "seedDryRun": (
            '& "$node24\\node.exe" "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js" '
            "run seed:generated -- --dry-run"
        ),
        "seedImport": (
            '& "$node24\\node.exe" "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js" '
            "run seed:generated"
        ),
        "seedVerify": (
            '& "$node24\\node.exe" "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js" '
            "run verify:generated-seed"
        ),
    }


def prefixed_errors(step_name: str, errors: list[Any]) -> list[str]:
    if not errors:
        return [f"{step_name}: failed without a detailed error"]
    return [f"{step_name}: {error}" for error in errors]


def default_schema_output_dir(html_path: Path) -> Path:
    return DEFAULT_RUN_OUTPUT_ROOT / safe_slug(html_path.stem)


def safe_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "html-page"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run schema generation, snapshot check, schema copy, and seed generation "
            "for the local Strapi sandbox."
        ),
    )
    parser.add_argument(
        "html_file",
        help="Path to the HTML file to inspect.",
    )
    parser.add_argument(
        "--target-dir",
        default=str(DEFAULT_SANDBOX_TARGET),
        help="Target Strapi app directory. Defaults to the sibling apps/strapi-sandbox directory.",
    )
    parser.add_argument(
        "--schema-output-dir",
        help="Directory where generated Strapi schema files should be written. Defaults to generated/strapi.",
    )
    parser.add_argument(
        "--seed-output-dir",
        help="Directory where generated Strapi seed files should be written. Defaults to generated/strapi/seed.",
    )
    parser.add_argument(
        "--snapshot",
        default=str(DEFAULT_SNAPSHOT_PATH),
        help="Schema snapshot JSON path. Defaults to snapshots/landing-page-1-schema-report.json.",
    )
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="Skip snapshot checking. Useful when validating a different HTML file without a saved snapshot.",
    )
    parser.add_argument(
        "--dry-run-copy",
        action="store_true",
        help="Validate and report schema copy operations without writing into the Strapi app.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the configured LLM planner. By default this command uses the deterministic planner.",
    )
    parser.add_argument(
        "--use-llm-section-analysis",
        action="store_true",
        help=(
            "Enrich each detected section with an LLM before CMS planning. "
            "This can be used with or without --use-llm."
        ),
    )
    parser.add_argument(
        "--status",
        choices=("draft", "published"),
        default="published",
        help="Document status to request during seed import.",
    )
    parser.add_argument(
        "--no-draft-and-publish",
        action="store_true",
        help="Set Strapi options.draftAndPublish to false in the generated content type schema.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    report = run_strapi_sandbox_pipeline(
        args.html_file,
        target_dir=args.target_dir,
        schema_output_dir=args.schema_output_dir,
        seed_output_dir=args.seed_output_dir,
        snapshot_path=args.snapshot,
        use_llm=args.use_llm,
        use_llm_section_analysis=args.use_llm_section_analysis,
        skip_snapshot=args.skip_snapshot,
        dry_run_copy=args.dry_run_copy,
        status=args.status,
        draft_and_publish=not args.no_draft_and_publish,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["isValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
