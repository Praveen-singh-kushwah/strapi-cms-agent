# AI Agent

The AI agent service will analyze uploaded HTML, detect page sections, generate structured Strapi schema plans, and validate agent outputs before review.

## Notebook MVP Planner

The current planner flow is:

```text
sample HTML -> deterministic HTML inspection -> optional LLM planner -> validated CMS plan JSON
```

By default, the planner can run locally without an API key using the deterministic fallback.

To enable the real OpenAI planner, copy `.env.example` to `.env` and set:

```text
OPENAI_API_KEY=your_api_key
MODEL_NAME=gpt-5.4-mini
LLM_PROVIDER=openai
USE_LLM_PLANNER=true
```

To use OpenRouter instead, set:

```text
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL_NAME=~openai/gpt-latest
LLM_PROVIDER=openrouter
LLM_MAX_TOKENS=4096
LLM_STRUCTURED_OUTPUT_MODE=json_schema
LLM_COMPACT_INPUT=true
USE_LLM_PLANNER=true
```

If your OpenRouter provider returns empty output with strict schemas, try:

```text
LLM_STRUCTURED_OUTPUT_MODE=json_object
```

You can also keep an OpenRouter key in `OPENAI_API_KEY`; keys that start with `sk-or-` are detected as OpenRouter automatically.

Run from this directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -c "from src.section_detector import analyze_html_file; from src.schema_planner import llm_section_planner_node; a=analyze_html_file('notebooks/sample-html/landing-page-1.html'); s=llm_section_planner_node({'html_analysis': a, 'errors': []}); print(s.get('errors') or s['cms_plan'])"
```

To generate a validation report for the plan:

```powershell
python -c "from src.section_detector import analyze_html_file; from src.schema_planner import llm_section_planner_node; from src.schema_validator import validate_cms_plan; import json; a=analyze_html_file('notebooks/sample-html/landing-page-1.html'); s=llm_section_planner_node({'html_analysis': a, 'errors': []}); print(json.dumps(s.get('errors') or validate_cms_plan(s['cms_plan']), indent=2))"
```

To generate Strapi schema files into the safe local output folder, use the helper command:

```powershell
python -m src.generate_strapi_schemas notebooks/sample-html/landing-page-1.html
```

The helper uses the deterministic planner by default. To use the configured LLM planner explicitly:

```powershell
python -m src.generate_strapi_schemas notebooks/sample-html/landing-page-1.html --use-llm
```

Generated schema files are written under:

```text
generated/strapi/
```

To compare current generated schema output against the saved reference snapshot:

```powershell
python -m src.check_schema_snapshot notebooks/sample-html/landing-page-1.html
```

If the intended schema output changes, update the snapshot with:

```powershell
python -m src.check_schema_snapshot notebooks/sample-html/landing-page-1.html --update
```

To copy generated schema files into a local Strapi app:

```powershell
python -m src.copy_schemas_to_strapi ..\strapi-sandbox --dry-run
python -m src.copy_schemas_to_strapi ..\strapi-sandbox
```

To run the AI-side sandbox preparation flow in one command:

```powershell
python -m src.run_strapi_sandbox_pipeline notebooks/sample-html/landing-page-1.html
```

This generates schemas, checks the schema snapshot, copies schemas into the sandbox, and writes the generated seed payload.

Then run the Strapi-side validation from `..\strapi-sandbox`:

```powershell
& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run validate:generated
```

For the full Strapi sandbox validation flow, including schema copy, seed generation, seed import, and readback verification, see:

```text
..\..\docs\strapi-sandbox-workflow.md
```
