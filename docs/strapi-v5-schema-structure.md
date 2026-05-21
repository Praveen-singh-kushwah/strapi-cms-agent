# Strapi v5 Schema File Structure

This note explains the Strapi v5 file structure that the future Strapi worker will generate from a validated CMS plan.

## Source References

- Strapi v5 project structure: https://docs.strapi.io/cms/project-structure
- Strapi v5 models: https://docs.strapi.io/cms/backend-customization/models

## Project Areas We Care About

A Strapi project stores generated schema files under `src/`.

```text
src/
  api/
    [api-name]/
      content-types/
        [content-type-name]/
          schema.json

  components/
    [category-name]/
      [component-name].json
```

For this project, the Strapi worker will eventually generate:

- content type `schema.json` files for page models
- component JSON files for reusable page sections and nested card/item components

Note: This document only covers schema files. A later worker may also manage Strapi route, controller, and service files for generated APIs when the automation flow needs explicit API scaffolding:

```text
src/api/[api-name]/routes/[api-name].ts
src/api/[api-name]/controllers/[api-name].ts
src/api/[api-name]/services/[api-name].ts
```

## Content Type Schema Location

Content types are stored here:

```text
src/api/[api-name]/content-types/[content-type-name]/schema.json
```

For a generated landing page single type:

```text
src/api/launch-flow-landing-page/
  content-types/
    launch-flow-landing-page/
      schema.json
```

The content type schema defines the main page model, such as:

- `kind`
- `collectionName`
- `info`
- `options`
- `attributes`

Example shape:

```json
{
  "kind": "singleType",
  "collectionName": "launch_flow_landing_pages",
  "info": {
    "singularName": "launch-flow-landing-page",
    "pluralName": "launch-flow-landing-pages",
    "displayName": "LaunchFlow Landing Page",
    "description": "Single type for the LaunchFlow marketing landing page."
  },
  "options": {
    "draftAndPublish": true
  },
  "pluginOptions": {},
  "attributes": {
    "hero": {
      "type": "component",
      "component": "landing-page.hero",
      "repeatable": false
    }
  }
}
```

## Component Schema Location

Components are stored here:

```text
src/components/[category-name]/[component-name].json
```

For a component UID:

```text
landing-page.hero
```

the future generated file should be:

```text
src/components/landing-page/hero.json
```

Example component schema:

```json
{
  "collectionName": "components_landing_page_hero",
  "info": {
    "displayName": "Hero"
  },
  "pluginOptions": {},
  "attributes": {
    "title": {
      "type": "string",
      "required": true
    },
    "description": {
      "type": "text"
    },
    "image": {
      "type": "media",
      "multiple": false,
      "allowedTypes": ["images"]
    }
  }
}
```

## CMS Plan to Strapi File Mapping

The current AI agent produces a CMS plan with these major parts:

```json
{
  "pageModel": {},
  "components": [],
  "singleTypeAttributes": [],
  "seedData": {},
  "warnings": []
}
```

The future Strapi worker should map them like this:

| CMS plan field | Strapi output |
| --- | --- |
| `pageModel` | `src/api/[apiName]/content-types/[singularName]/schema.json` |
| `components[]` | `src/components/[category]/[fileName].json` |
| `singleTypeAttributes[]` | `attributes` inside the page content type schema |
| `seedData` | later seed/content import step, not schema files |
| `warnings` | review/debug metadata, not schema files |

For generated content type schemas, prefer plural-style `collectionName` values, even for single types, for consistency with common Strapi table naming conventions. For example:

```text
launch_flow_landing_pages
```

Also include a `pluginOptions` object in generated schemas, even when it is empty, so generated files remain easy to extend later.

## Example Mapping

CMS plan component:

```json
{
  "uid": "landing-page.feature-card",
  "category": "landing-page",
  "fileName": "feature-card",
  "displayName": "Feature Card"
}
```

Future Strapi file:

```text
src/components/landing-page/feature-card.json
```

CMS plan page model:

```json
{
  "kind": "singleType",
  "apiName": "launch-flow-landing-page",
  "singularName": "launch-flow-landing-page",
  "pluralName": "launch-flow-landing-pages",
  "displayName": "LaunchFlow Landing Page"
}
```

Future Strapi file:

```text
src/api/launch-flow-landing-page/content-types/launch-flow-landing-page/schema.json
```

## What We Are Not Doing Yet

This step does not:

- install Strapi
- create a Strapi project
- write generated schema files
- restart Strapi
- seed content into Strapi

Those actions belong to later Strapi worker steps after the schema preview and validation flow is designed.
