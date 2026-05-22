# Strapi Sandbox Workflow

This document is the current executable workflow for validating generated Strapi schemas and seed content in the local sandbox app.

## Purpose

The sandbox lets us test generated output safely before touching a real Strapi project.

The workflow validates that:

- the AI agent can generate Strapi v5 schema files
- generated schemas can be copied into a real Strapi app
- Strapi can build and boot with those schemas
- generated seed content can be imported into the Landing Page single type
- imported content can be read back from Strapi, including linked media fields

## Project Paths

```text
D:\strapi-cms-agent\apps\ai-agent
D:\strapi-cms-agent\apps\strapi-sandbox
```

Generated agent output is written under:

```text
D:\strapi-cms-agent\apps\ai-agent\generated\strapi
```

The sandbox reads schemas from:

```text
D:\strapi-cms-agent\apps\strapi-sandbox\src
```

## Node Version

Strapi v5 supports Node 20 through Node 24. The sandbox should be run with the bundled Node 24 runtime, not system Node 25.

From `D:\strapi-cms-agent\apps\strapi-sandbox`, set:

```powershell
$node24 = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$env:Path = "$node24;$env:Path"
$env:XDG_CONFIG_HOME = "$PWD\.xdg-config"
$env:STRAPI_TELEMETRY_DISABLED = "true"
```

Then run npm through that Node runtime:

```powershell
& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run dev
```

## Step 1: Generate Strapi Schemas

From the AI agent app:

```powershell
cd D:\strapi-cms-agent\apps\ai-agent
.\.venv\Scripts\python.exe -m src.generate_strapi_schemas notebooks/sample-html/landing-page-1.html
```

Expected result:

```json
{
  "isValid": true,
  "errors": []
}
```

This writes files under:

```text
D:\strapi-cms-agent\apps\ai-agent\generated\strapi\src
```

## Step 2: Check Schema Snapshot

From the AI agent app:

```powershell
.\.venv\Scripts\python.exe -m src.check_schema_snapshot notebooks/sample-html/landing-page-1.html
```

Expected result:

```json
{
  "isValid": true,
  "matchesSnapshot": true
}
```

If the intended generated schema output changes, update the snapshot explicitly:

```powershell
.\.venv\Scripts\python.exe -m src.check_schema_snapshot notebooks/sample-html/landing-page-1.html --update
```

## Step 3: Copy Schemas Into The Sandbox

From the repo root:

```powershell
cd D:\strapi-cms-agent
Copy-Item -Path apps\ai-agent\generated\strapi\src\api\* -Destination apps\strapi-sandbox\src\api -Recurse -Force
Copy-Item -Path apps\ai-agent\generated\strapi\src\components\* -Destination apps\strapi-sandbox\src\components -Recurse -Force
```

This updates the sandbox schema files only. It does not import content.

## Step 4: Build The Sandbox

From the sandbox app:

```powershell
cd D:\strapi-cms-agent\apps\strapi-sandbox
$node24 = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$env:Path = "$node24;$env:Path"
$env:XDG_CONFIG_HOME = "$PWD\.xdg-config"
$env:STRAPI_TELEMETRY_DISABLED = "true"

& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run build
```

If the build succeeds, Strapi accepted the generated schema structure.

## Step 5: Generate Seed Payload

From the AI agent app:

```powershell
cd D:\strapi-cms-agent\apps\ai-agent
.\.venv\Scripts\python.exe -m src.generate_strapi_seed notebooks/sample-html/landing-page-1.html
```

This writes:

```text
D:\strapi-cms-agent\apps\ai-agent\generated\strapi\seed\landing-page.seed.json
```

The seed payload contains:

- Strapi content type UID
- single type field data
- media asset references
- resolved media upload plan
- seed warnings

## Step 6: Dry Run Seed Import

Stop the Strapi dev server before running import or verification commands. The sandbox uses SQLite, and only one Strapi process should access the database at a time.

From the sandbox app:

```powershell
cd D:\strapi-cms-agent\apps\strapi-sandbox
$node24 = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$env:Path = "$node24;$env:Path"
$env:XDG_CONFIG_HOME = "$PWD\.xdg-config"
$env:STRAPI_TELEMETRY_DISABLED = "true"

& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run seed:generated -- --dry-run
```

Expected result:

```json
{
  "isValid": true,
  "dryRun": true
}
```

The dry run validates the seed file path, UID, data keys, and media plan. It does not write to Strapi.

## Step 7: Import Seed Content

From the sandbox app, with the dev server stopped:

```powershell
& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run seed:generated
```

Expected result:

```json
{
  "isValid": true,
  "dryRun": false,
  "importReport": {
    "action": "created"
  }
}
```

If content already exists, the action can be:

```text
updated
```

The importer also uploads or reuses ready media files and links uploaded media IDs into nested seed data.

## Step 8: Verify Imported Content

From the sandbox app, with the dev server stopped:

```powershell
& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run verify:generated-seed
```

Expected result:

```json
{
  "isValid": true,
  "errors": [],
  "warnings": [],
  "summary": {
    "verifiedMediaFields": [
      "hero.image"
    ]
  }
}
```

This reads the Landing Page single type back from Strapi and validates that expected seed data persisted.

## Step 9: Run The Admin UI

From the sandbox app:

```powershell
& "$node24\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run dev
```

Open:

```text
http://localhost:1337/admin
```

Confirm:

- `Landing Page` single type exists
- generated components exist
- seeded content appears in the single type
- hero image is linked in the media field

## Success Criteria

The full sandbox validation is successful when:

- schema generation returns `isValid: true`
- snapshot check returns `matchesSnapshot: true`
- sandbox build succeeds
- seed dry run returns `isValid: true`
- seed import returns `isValid: true`
- seed readback verification returns `isValid: true`
- Strapi Admin shows the generated content type, components, seed data, and media link

## Current Limitations

- Schema copying is still manual.
- The sandbox is local and disposable.
- Seed import targets the generated Landing Page single type only.
- Header and footer global blocks are planned separately and are not imported in this seed flow.
- Production Strapi integration is not implemented yet.
