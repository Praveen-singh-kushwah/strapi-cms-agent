"""Run the full local Strapi sandbox validation flow from the repo root."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AI_AGENT_DIR = REPO_ROOT / "apps" / "ai-agent"
STRAPI_SANDBOX_DIR = REPO_ROOT / "apps" / "strapi-sandbox"
DEFAULT_HTML_FILE = Path("notebooks") / "sample-html" / "landing-page-1.html"
DEFAULT_NODE_BIN = Path(
    r"C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
)
DEFAULT_NPM_CLI = Path(r"C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js")


def run_full_validation(
    html_file: str | Path = DEFAULT_HTML_FILE,
    *,
    ai_python: str | Path | None = None,
    node_bin: str | Path | None = None,
    npm_cli: str | Path | None = None,
    use_llm: bool = False,
    skip_snapshot: bool = False,
    dry_run_copy: bool = False,
    skip_import: bool = False,
) -> dict[str, Any]:
    """Run AI-side preparation and Strapi-side validation as one workflow."""
    html_path = Path(html_file)
    python_path = resolve_ai_python(ai_python)
    node_path = resolve_node_path(node_bin)
    npm_cli_path = resolve_npm_cli(npm_cli)
    report: dict[str, Any] = {
        "isValid": False,
        "repoRoot": str(REPO_ROOT),
        "htmlFile": str(html_path),
        "steps": {
            "aiPipeline": None,
            "strapiValidation": None,
        },
        "runtime": {
            "aiPython": str(python_path),
            "node": str(node_path),
            "npmCli": str(npm_cli_path) if npm_cli_path else None,
        },
        "errors": [],
    }

    setup_errors = validate_runtime_paths(python_path, node_path, npm_cli_path)
    if setup_errors:
        report["errors"] = setup_errors
        return report

    ai_command = build_ai_pipeline_command(
        python_path,
        html_path,
        use_llm=use_llm,
        skip_snapshot=skip_snapshot,
        dry_run_copy=dry_run_copy,
    )
    ai_result = run_json_command(
        "aiPipeline",
        ai_command,
        cwd=AI_AGENT_DIR,
        env=os.environ.copy(),
    )
    report["steps"]["aiPipeline"] = summarize_result(ai_result)
    if not ai_result["isValid"]:
        report["errors"] = prefixed_errors("aiPipeline", ai_result)
        return report

    strapi_command = build_strapi_validation_command(node_path, skip_import=skip_import)
    strapi_result = run_json_command(
        "strapiValidation",
        strapi_command,
        cwd=STRAPI_SANDBOX_DIR,
        env=build_strapi_env(node_path.parent, npm_cli_path),
    )
    report["steps"]["strapiValidation"] = summarize_result(strapi_result)
    if not strapi_result["isValid"]:
        report["errors"] = prefixed_errors("strapiValidation", strapi_result)
        return report

    report["isValid"] = True
    return report


def resolve_ai_python(ai_python: str | Path | None) -> Path:
    if ai_python is not None:
        return Path(ai_python)

    if sys.platform == "win32":
        return AI_AGENT_DIR / ".venv" / "Scripts" / "python.exe"

    return AI_AGENT_DIR / ".venv" / "bin" / "python"


def resolve_node_path(node_bin: str | Path | None) -> Path:
    configured_node_bin = node_bin or os.environ.get("STRAPI_SANDBOX_NODE_BIN")
    if configured_node_bin:
        bin_path = Path(configured_node_bin)
        return bin_path / ("node.exe" if sys.platform == "win32" else "node")

    if DEFAULT_NODE_BIN.exists():
        return DEFAULT_NODE_BIN / "node.exe"

    return Path("node.exe" if sys.platform == "win32" else "node")


def resolve_npm_cli(npm_cli: str | Path | None) -> Path | None:
    configured_npm_cli = npm_cli or os.environ.get("STRAPI_SANDBOX_NPM_CLI")
    if configured_npm_cli:
        return Path(configured_npm_cli)

    if DEFAULT_NPM_CLI.exists():
        return DEFAULT_NPM_CLI

    return None


def validate_runtime_paths(python_path: Path, node_path: Path, npm_cli_path: Path | None) -> list[str]:
    errors = []

    if not python_path.exists():
        errors.append(f"AI agent Python was not found: {python_path}")

    if node_path.is_absolute() and not node_path.exists():
        errors.append(f"Node runtime was not found: {node_path}")

    if npm_cli_path is not None and not npm_cli_path.exists():
        errors.append(f"npm CLI was not found: {npm_cli_path}")

    if not (STRAPI_SANDBOX_DIR / "scripts" / "validate-generated.js").exists():
        errors.append("Strapi generated validation script was not found")

    return errors


def build_ai_pipeline_command(
    python_path: Path,
    html_file: Path,
    *,
    use_llm: bool,
    skip_snapshot: bool,
    dry_run_copy: bool,
) -> list[str]:
    command = [
        str(python_path),
        "-m",
        "src.run_strapi_sandbox_pipeline",
        str(html_file),
    ]

    if use_llm:
        command.append("--use-llm")
    if skip_snapshot:
        command.append("--skip-snapshot")
    if dry_run_copy:
        command.append("--dry-run-copy")

    return command


def build_strapi_validation_command(node_path: Path, *, skip_import: bool) -> list[str]:
    command = [
        str(node_path),
        str(STRAPI_SANDBOX_DIR / "scripts" / "validate-generated.js"),
    ]
    if skip_import:
        command.append("--skip-import")
    return command


def build_strapi_env(node_bin: Path, npm_cli_path: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{node_bin}{os.pathsep}{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(STRAPI_SANDBOX_DIR / ".xdg-config")
    env["STRAPI_TELEMETRY_DISABLED"] = "true"
    if npm_cli_path is not None:
        env["npm_execpath"] = str(npm_cli_path)
    return env


def run_json_command(
    step_name: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    parsed_json = parse_last_json_object(output)

    result = {
        "step": step_name,
        "command": command,
        "exitCode": completed.returncode,
        "isValid": completed.returncode == 0,
        "report": parsed_json,
        "outputPreview": tail(output),
    }

    if parsed_json is None:
        result["isValid"] = False
        result["error"] = f"{step_name} did not return a parseable JSON report"
    elif parsed_json.get("isValid") is not True:
        result["isValid"] = False
        result["error"] = f"{step_name} returned isValid=false"

    return result


def parse_last_json_object(output: str) -> dict[str, Any] | None:
    text = strip_ansi(output).strip()
    if not text:
        return None

    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            value = json.loads(text[index:])
        except json.JSONDecodeError:
            continue
        return value if isinstance(value, dict) else None

    return None


def strip_ansi(value: str) -> str:
    # Good enough for Strapi/npm color codes in captured output.
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", value)


def tail(value: str, limit: int = 3000) -> str:
    stripped = strip_ansi(value).strip()
    return stripped if len(stripped) <= limit else stripped[-limit:]


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "isValid": result["isValid"],
        "exitCode": result["exitCode"],
    }
    if result.get("report") is not None:
        summary["report"] = result["report"]
    if result.get("error"):
        summary["error"] = result["error"]
        summary["outputPreview"] = result["outputPreview"]
    return summary


def prefixed_errors(step_name: str, result: dict[str, Any]) -> list[str]:
    report = result.get("report")
    if isinstance(report, dict) and report.get("errors"):
        return [f"{step_name}: {error}" for error in report["errors"]]
    if result.get("error"):
        return [f"{step_name}: {result['error']}"]
    return [f"{step_name}: command failed with exit code {result['exitCode']}"]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the full AI-agent plus Strapi sandbox validation workflow.",
    )
    parser.add_argument(
        "--html-file",
        default=str(DEFAULT_HTML_FILE),
        help="HTML file path relative to apps/ai-agent. Defaults to the landing-page sample.",
    )
    parser.add_argument(
        "--ai-python",
        help="Path to the AI agent Python executable. Defaults to apps/ai-agent/.venv.",
    )
    parser.add_argument(
        "--node-bin",
        help="Directory containing the Node executable for Strapi. Defaults to the bundled Node 24 path when present.",
    )
    parser.add_argument(
        "--npm-cli",
        help="Path to npm-cli.js. Defaults to the globally installed npm CLI when present.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the configured LLM planner for the AI-side pipeline.",
    )
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="Skip schema snapshot checking in the AI-side pipeline.",
    )
    parser.add_argument(
        "--dry-run-copy",
        action="store_true",
        help="Preview schema copy without writing into the Strapi sandbox.",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Run Strapi build, seed dry-run, and readback verification without importing seed data.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    report = run_full_validation(
        args.html_file,
        ai_python=args.ai_python,
        node_bin=args.node_bin,
        npm_cli=args.npm_cli,
        use_llm=args.use_llm,
        skip_snapshot=args.skip_snapshot,
        dry_run_copy=args.dry_run_copy,
        skip_import=args.skip_import,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["isValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
