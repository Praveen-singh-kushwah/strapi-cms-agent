"""Compare generated Strapi schema output against a saved snapshot."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

from src.generate_strapi_schemas import generate_strapi_schema_report


AI_AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_PATH = AI_AGENT_ROOT / "snapshots" / "landing-page-1-schema-report.json"


def generate_schema_snapshot(
    html_file: str | Path,
    *,
    output_dir: str | Path | None = None,
    use_llm: bool = False,
    draft_and_publish: bool = True,
) -> dict[str, Any]:
    """Generate a stable snapshot report from the full schema generation report."""
    report = generate_strapi_schema_report(
        html_file,
        output_dir=output_dir,
        use_llm=use_llm,
        draft_and_publish=draft_and_publish,
    )
    return normalize_schema_report(report)


def normalize_schema_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove machine-specific paths while preserving schema-shape signals."""
    return {
        "isValid": report.get("isValid", False),
        "usedLLM": report.get("usedLLM", False),
        "planValidation": normalize_plan_validation(report.get("planValidation")),
        "writeReport": normalize_write_report(report.get("writeReport")),
        "generatedValidation": normalize_generated_validation(report.get("generatedValidation")),
        "errors": report.get("errors", []),
    }


def normalize_plan_validation(plan_validation: Any) -> dict[str, Any] | None:
    if not isinstance(plan_validation, dict):
        return None
    return {
        "isValid": plan_validation.get("isValid", False),
        "errors": plan_validation.get("errors", []),
        "warnings": plan_validation.get("warnings", []),
        "summary": plan_validation.get("summary", {}),
    }


def normalize_write_report(write_report: Any) -> dict[str, Any] | None:
    if not isinstance(write_report, dict):
        return None
    return {
        "fileCount": write_report.get("fileCount", 0),
        "files": write_report.get("files", []),
    }


def normalize_generated_validation(generated_validation: Any) -> dict[str, Any] | None:
    if not isinstance(generated_validation, dict):
        return None

    summary = generated_validation.get("summary", {})
    if isinstance(summary, dict):
        summary = {
            "fileCount": summary.get("fileCount", 0),
            "files": summary.get("files", []),
        }

    return {
        "isValid": generated_validation.get("isValid", False),
        "errors": generated_validation.get("errors", []),
        "warnings": generated_validation.get("warnings", []),
        "summary": summary,
    }


def check_schema_snapshot(
    html_file: str | Path,
    *,
    snapshot_path: str | Path = DEFAULT_SNAPSHOT_PATH,
    output_dir: str | Path | None = None,
    use_llm: bool = False,
    draft_and_publish: bool = True,
) -> dict[str, Any]:
    """Compare the current generated schema snapshot with an expected snapshot file."""
    snapshot_file = Path(snapshot_path)
    current = generate_schema_snapshot(
        html_file,
        output_dir=output_dir,
        use_llm=use_llm,
        draft_and_publish=draft_and_publish,
    )

    if not snapshot_file.exists():
        return {
            "isValid": False,
            "matchesSnapshot": False,
            "snapshotPath": str(snapshot_file),
            "errors": [f"Snapshot file does not exist: {snapshot_file}"],
            "diff": [],
        }

    expected = json.loads(snapshot_file.read_text(encoding="utf-8"))
    matches = expected == current
    return {
        "isValid": matches and current.get("isValid", False),
        "matchesSnapshot": matches,
        "snapshotPath": str(snapshot_file),
        "errors": [] if matches else ["Generated schema snapshot does not match expected snapshot"],
        "diff": [] if matches else build_snapshot_diff(expected, current),
    }


def update_schema_snapshot(
    html_file: str | Path,
    *,
    snapshot_path: str | Path = DEFAULT_SNAPSHOT_PATH,
    output_dir: str | Path | None = None,
    use_llm: bool = False,
    draft_and_publish: bool = True,
) -> dict[str, Any]:
    """Write the current generated schema snapshot to disk."""
    snapshot_file = Path(snapshot_path)
    snapshot = generate_schema_snapshot(
        html_file,
        output_dir=output_dir,
        use_llm=use_llm,
        draft_and_publish=draft_and_publish,
    )
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)
    snapshot_file.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "isValid": snapshot.get("isValid", False),
        "snapshotUpdated": True,
        "snapshotPath": str(snapshot_file),
        "summary": {
            "writeFileCount": (snapshot.get("writeReport") or {}).get("fileCount", 0),
            "generatedFileCount": ((snapshot.get("generatedValidation") or {}).get("summary") or {}).get(
                "fileCount",
                0,
            ),
        },
        "errors": snapshot.get("errors", []),
    }


def build_snapshot_diff(expected: dict[str, Any], current: dict[str, Any]) -> list[str]:
    expected_lines = json.dumps(expected, indent=2, sort_keys=True).splitlines()
    current_lines = json.dumps(current, indent=2, sort_keys=True).splitlines()
    return list(
        difflib.unified_diff(
            expected_lines,
            current_lines,
            fromfile="expected",
            tofile="current",
            lineterm="",
        )
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare generated Strapi schema output against a saved snapshot.",
    )
    parser.add_argument(
        "html_file",
        help="Path to the HTML file to inspect.",
    )
    parser.add_argument(
        "--snapshot",
        default=str(DEFAULT_SNAPSHOT_PATH),
        help="Snapshot JSON path. Defaults to snapshots/landing-page-1-schema-report.json.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where generated Strapi schema files should be written. Defaults to generated/strapi.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update the snapshot instead of checking against it.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the configured LLM planner. Snapshot checks should usually stay deterministic.",
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

    common_args = {
        "snapshot_path": args.snapshot,
        "output_dir": args.output_dir,
        "use_llm": args.use_llm,
        "draft_and_publish": not args.no_draft_and_publish,
    }
    report = (
        update_schema_snapshot(args.html_file, **common_args)
        if args.update
        else check_schema_snapshot(args.html_file, **common_args)
    )

    print(json.dumps(report, indent=2))
    return 0 if report["isValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
