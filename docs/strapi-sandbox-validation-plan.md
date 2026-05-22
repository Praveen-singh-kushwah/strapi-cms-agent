# Strapi Sandbox Validation Plan

This document explains how we will validate generated Strapi schema files inside a safe local Strapi app before touching any real project.

## Purpose

The AI agent can now generate Strapi-compatible schema files under:

```text
apps/ai-agent/generated/strapi/
```

The next risk is whether a real Strapi application accepts those files when it boots.

To test that safely, we will create a separate sandbox app:

```text
apps/strapi-sandbox/
```

The sandbox is a disposable test project. If generated schemas are wrong, only the sandbox breaks. Existing or future production Strapi projects stay untouched.

## Source References

- Strapi v5 project structure: https://docs.strapi.io/cms/project-structure
- Strapi v5 models: https://docs.strapi.io/cms/backend-customization/models
- Strapi documentation landing page: https://docs.strapi.io/
- Strapi create app package: https://www.npmjs.com/package/create-strapi-app

## Validation Flow

The sandbox validation flow is:

```text
sample HTML
  -> AI agent schema generation
  -> generated/strapi files
  -> copy schemas into apps/strapi-sandbox
  -> run Strapi sandbox
  -> confirm Strapi accepts the schemas
```

## Step 1: Create Sandbox App

Create a new Strapi app under:

```text
apps/strapi-sandbox/
```

This step requires Node.js, npm, and internet access because Strapi dependencies need to be downloaded.

The exact create command should be checked against the current Strapi docs before execution. The current Strapi v5 ecosystem commonly uses a create command such as:

```powershell
npx create-strapi@latest apps/strapi-sandbox --quickstart
```

or the create-strapi-app package:

```powershell
npx create-strapi-app@latest apps/strapi-sandbox
```

We should choose one command only when we actually perform the installation step.

## Step 2: Generate Schemas

From the AI agent app:

```powershell
cd apps/ai-agent
python -m src.generate_strapi_schemas notebooks/sample-html/landing-page-1.html
```

This writes generated schemas to:

```text
apps/ai-agent/generated/strapi/
```

Expected validation result:

```json
{
  "isValid": true,
  "generatedValidation": {
    "isValid": true,
    "errors": []
  }
}
```

## Step 3: Copy Generated Schemas Into Sandbox

Copy:

```text
apps/ai-agent/generated/strapi/src/api/
apps/ai-agent/generated/strapi/src/components/
```

into:

```text
apps/strapi-sandbox/src/api/
apps/strapi-sandbox/src/components/
```

For the MVP, this can be manual or scripted later.

Later automation can provide a command like:

```powershell
python -m src.copy_schemas_to_strapi --target ..\strapi-sandbox
```

That copy helper is not implemented yet.

## Step 4: Run The Sandbox

From the sandbox app:

```powershell
cd apps/strapi-sandbox
npm run develop
```

If Strapi starts without schema errors, it means the generated schema files are structurally acceptable to Strapi.

## Step 5: Verify In Admin UI

Open:

```text
http://localhost:1337/admin
```

Check that the generated structures appear as expected:

- `Landing Page` single type exists
- `Hero`, `Features`, `Pricing`, `FAQ`, and `Contact` components exist
- shared `Link` and `SEO` components exist
- component fields match the generated schema plan
- Strapi does not report schema loading errors

## Success Criteria

The sandbox validation is successful when:

- generated schema command returns `isValid: true`
- generated snapshot check returns `matchesSnapshot: true`
- generated schemas are copied into the sandbox app
- Strapi starts successfully
- Strapi Admin shows the generated content type and components
- no real Strapi project was modified

## What This Step Does Not Do

This plan does not:

- create the sandbox app yet
- install Strapi dependencies yet
- copy generated schemas yet
- seed content into Strapi
- connect to a production database
- modify any real Strapi project

Those belong to later implementation steps.

## Recommended Next Steps

After this plan is reviewed:

```text
8.6.2 Create apps/strapi-sandbox
8.6.3 Add a schema copy helper
8.6.4 Copy generated schemas into sandbox
8.6.5 Run Strapi and verify boot
8.6.6 Verify generated types in Strapi Admin
```
