"""Command-line helper for generating Strapi seed content from an HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.schema_planner import llm_section_planner_node
from src.schema_validator import validate_cms_plan
from src.section_detector import analyze_html_file
from src.strapi_seed_generator import write_strapi_seed_file


def generate_strapi_seed_report(
    html_file: str | Path,
    *,
    output_dir: str | Path | None = None,
    use_llm: bool = False,
    status: str = "published",
) -> dict[str, Any]:
    """Run the HTML -> CMS plan -> Strapi seed payload flow."""
    html_path = Path(html_file)
    report: dict[str, Any] = {
        "isValid": False,
        "htmlFile": str(html_path),
        "usedLLM": use_llm,
        "planValidation": None,
        "seedWriteReport": None,
        "errors": [],
    }

    try:
        analysis = analyze_html_file(html_path)
        state = llm_section_planner_node(
            {
                "html_analysis": analysis,
                "planner_context": {"useLLM": use_llm},
                "errors": [],
            }
        )
        if state.get("errors"):
            report["errors"] = state["errors"]
            return report

        cms_plan = state["cms_plan"]
        plan_validation = validate_cms_plan(cms_plan)
        report["planValidation"] = plan_validation
        if not plan_validation["isValid"]:
            report["errors"] = plan_validation["errors"]
            return report

        seed_write_report = write_strapi_seed_file(
            cms_plan,
            output_dir=output_dir,
            status=status,
        )
        report["seedWriteReport"] = seed_write_report
        report["isValid"] = seed_write_report["validation"]["isValid"]
        report["errors"] = seed_write_report["validation"]["errors"]
        return report
    except Exception as exc:  # pragma: no cover - command-line safety net
        report["errors"] = [str(exc)]
        return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a Strapi seed JSON payload from an inspected HTML page.",
    )
    parser.add_argument(
        "html_file",
        help="Path to the HTML file to inspect.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where the generated Strapi seed file should be written. Defaults to generated/strapi/seed.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the configured LLM planner. By default this command uses the deterministic planner.",
    )
    parser.add_argument(
        "--status",
        choices=("draft", "published"),
        default="published",
        help="Document status to request during import.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    report = generate_strapi_seed_report(
        args.html_file,
        output_dir=args.output_dir,
        use_llm=args.use_llm,
        status=args.status,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["isValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
