# Strapi CMS Agent Handoff

This handoff summarizes the current state of the `strapi-cms-agent` workspace so another Windows system can continue the work in a new Codex thread.

## Workspace

Repo path used in this thread:

```text
D:\strapi-cms-agent
```

Main apps:

```text
D:\strapi-cms-agent\apps\ai-agent
D:\strapi-cms-agent\apps\strapi-sandbox
```

The AI agent converts sample HTML into Strapi CMS plans, schema files, seed payloads, and sandbox validation output.

## Current Working Flow

The current happy path is:

```text
HTML file
  -> deterministic HTML inspection
  -> CMS plan generation
  -> CMS plan validation
  -> Strapi schema generation
  -> schema copy into Strapi sandbox
  -> seed payload generation
  -> Strapi build
  -> seed dry-run
  -> seed import
  -> readback verification
```

The full repo-level validation command is:

```powershell
cd D:\strapi-cms-agent
python scripts\validate_strapi_sandbox.py
```

Expected result:

```json
{
  "isValid": true,
  "errors": []
}
```

To validate a different HTML file before a snapshot exists:

```powershell
python scripts\validate_strapi_sandbox.py --html-file notebooks\sample-html\cost-optimization.html --skip-snapshot
```

The `--html-file` path is relative to:

```text
D:\strapi-cms-agent\apps\ai-agent
```

## Important Commands

AI-side one-command preparation:

```powershell
cd D:\strapi-cms-agent\apps\ai-agent
.\.venv\Scripts\python.exe -m src.run_strapi_sandbox_pipeline notebooks/sample-html/landing-page-1.html
```

Strapi-side one-command validation:

```powershell
cd D:\strapi-cms-agent\apps\strapi-sandbox
npm run validate:generated
```

Full repo-level validation:

```powershell
cd D:\strapi-cms-agent
python scripts\validate_strapi_sandbox.py
```

Skip seed import when content already exists:

```powershell
python scripts\validate_strapi_sandbox.py --skip-import
```

Use LLM planner mode:

```powershell
python scripts\validate_strapi_sandbox.py --use-llm
```

## Runtime Notes

Strapi v5 should run on Node 20 through Node 24. Do not use Node 25 for the sandbox.

This thread used a bundled Node 24 runtime:

```text
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin
```

Manual Strapi command setup:

```powershell
$node24 = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$env:Path = "$node24;$env:Path"
$env:XDG_CONFIG_HOME = "$PWD\.xdg-config"
$env:STRAPI_TELEMETRY_DISABLED = "true"
```

Then run npm through Node 24:

```powershell
& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run dev
```

## Setup On Another Windows System

After copying or cloning the repo, recreate the AI agent environment:

```powershell
cd D:\strapi-cms-agent\apps\ai-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install Strapi sandbox dependencies:

```powershell
cd D:\strapi-cms-agent\apps\strapi-sandbox
npm install
```

Copy local secret files manually if needed. Do not commit them:

```text
D:\strapi-cms-agent\apps\ai-agent\.env
D:\strapi-cms-agent\apps\strapi-sandbox\.env
```

To preserve the same Strapi sandbox admin/content/media state, also copy:

```text
D:\strapi-cms-agent\apps\strapi-sandbox\.tmp\data.db
D:\strapi-cms-agent\apps\strapi-sandbox\public\uploads
```

## Key Implemented Files

AI agent:

```text
apps\ai-agent\src\html_parser.py
apps\ai-agent\src\section_detector.py
apps\ai-agent\src\schema_models.py
apps\ai-agent\src\schema_planner.py
apps\ai-agent\src\schema_validator.py
apps\ai-agent\src\strapi_schema_generator.py
apps\ai-agent\src\strapi_seed_generator.py
apps\ai-agent\src\generate_strapi_schemas.py
apps\ai-agent\src\generate_strapi_seed.py
apps\ai-agent\src\copy_schemas_to_strapi.py
apps\ai-agent\src\run_strapi_sandbox_pipeline.py
apps\ai-agent\src\check_schema_snapshot.py
```

Strapi sandbox:

```text
apps\strapi-sandbox\scripts\import-generated-seed.js
apps\strapi-sandbox\scripts\verify-generated-seed.js
apps\strapi-sandbox\scripts\validate-generated.js
```

Repo-level validation:

```text
scripts\validate_strapi_sandbox.py
```

Docs:

```text
docs\strapi-v5-schema-structure.md
docs\cms-plan-contract.md
docs\cms-plan-to-strapi-mapping.md
docs\strapi-sandbox-validation-plan.md
docs\strapi-sandbox-workflow.md
```

## Generated Output Behavior

Generated outputs are written into per-HTML run folders:

```text
apps\ai-agent\generated\strapi\runs\[html-file-name]
```

This prevents stale schemas from different HTML pages from mixing together.

Examples:

```text
apps\ai-agent\generated\strapi\runs\landing-page-1
apps\ai-agent\generated\strapi\runs\cost-optimization
```

## Current Sample Pages

Primary known-good page:

```text
apps\ai-agent\notebooks\sample-html\landing-page-1.html
```

Second test page:

```text
apps\ai-agent\notebooks\sample-html\cost-optimization.html
```

The second page validates technically with:

```powershell
python scripts\validate_strapi_sandbox.py --html-file notebooks\sample-html\cost-optimization.html --skip-snapshot
```

But its deterministic plan is incomplete. It currently maps mostly:

```text
seo
hero
```

and warns that several sections could not be mapped.

## Known Limitation

The deterministic planner works well for `landing-page-1.html`, but for more complex or differently named pages, it may not map all semantic sections.

Example warnings from `cost-optimization.html`:

```text
Section 2 could not be mapped to a known component type.
Section 3 could not be mapped to a known component type.
...
```

This means the pipeline is technically valid, but the generated schema may be incomplete for real-world pages.

## Recommended Next Step

Improve section planning for non-LaunchFlow pages.

Good next options:

1. Improve deterministic section classification and generic section fallback components.
2. Add a richer LLM planner mode for unknown section types.
3. Add snapshots for the second sample after the desired expected output is decided.
4. Add validation that fails when too many detected sections are unmapped, so incomplete plans are not silently accepted.

Recommended immediate next task:

```text
Add a generic fallback section/component plan for unmapped but valid sections, or switch unknown section handling to the LLM planner.
```

## Suggested Prompt For New Codex Thread

Use this in the new system:

```text
Read HANDOFF.md and continue the strapi-cms-agent work from the recommended next step. First inspect the current repo state and verify the full validation command still passes.
```
