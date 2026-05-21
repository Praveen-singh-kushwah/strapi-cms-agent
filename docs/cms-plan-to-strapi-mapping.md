# CMS Plan to Strapi Schema Mapping

This note defines how the validated CMS plan produced by the AI agent should map to Strapi v5 schema files in a later generator step.

## Source References

- Strapi v5 models: https://docs.strapi.io/cms/backend-customization/models
- Strapi v5 project structure: https://docs.strapi.io/cms/project-structure
- Local schema structure note: ./strapi-v5-schema-structure.md

## Input Contract

The AI agent currently produces a CMS plan with this shape:

```json
{
  "pageModel": {},
  "seo": {},
  "globalBlocks": {},
  "components": [],
  "singleTypeAttributes": [],
  "seedData": {},
  "warnings": []
}
```

The Strapi worker should treat this as a planning contract, not as direct file content.

## High-Level Mapping

| CMS plan key | Purpose | Future Strapi output |
| --- | --- | --- |
| `pageModel` | Main generated page model metadata | Content type `schema.json` |
| `components[]` | Reusable component definitions | Component JSON files |
| `singleTypeAttributes[]` | Fields on the main page model | `attributes` inside content type schema |
| `seo` | Shared SEO component configuration | Page attribute referencing `shared.seo` |
| `globalBlocks` | Header/footer handling decision | Later global single types or ignored layout |
| `seedData` | Initial content values extracted from HTML | Later content seeding step |
| `warnings` | Review/debug metadata | Not written to Strapi schema files |

## Page Model Mapping

CMS plan:

```json
{
  "kind": "singleType",
  "apiName": "launch-flow-landing-page",
  "displayName": "LaunchFlow Landing Page",
  "singularName": "launch-flow-landing-page",
  "pluralName": "launch-flow-landing-pages",
  "description": "Single type for the LaunchFlow marketing landing page."
}
```

Future Strapi content type path:

```text
src/api/launch-flow-landing-page/content-types/launch-flow-landing-page/schema.json
```

Future Strapi schema shape:

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
  "attributes": {}
}
```

Mapping rules:

| CMS plan field | Strapi schema field |
| --- | --- |
| `kind` | `kind` |
| `apiName` | API folder name |
| `singularName` | content type folder name and `info.singularName` |
| `pluralName` | `info.pluralName` |
| `displayName` | `info.displayName` |
| `description` | `info.description` |

`collectionName` should be generated from `pluralName` by converting kebab-case to snake_case.

The generator should default `draftAndPublish` to `true` for page single types unless the CMS plan explicitly provides another value.

## Component Mapping

CMS plan component:

```json
{
  "uid": "landing-page.hero",
  "category": "landing-page",
  "displayName": "Hero",
  "fileName": "hero",
  "fields": []
}
```

Future Strapi component path:

```text
src/components/landing-page/hero.json
```

Future Strapi component shape:

```json
{
  "collectionName": "components_landing_page_hero",
  "info": {
    "displayName": "Hero"
  },
  "pluginOptions": {},
  "attributes": {}
}
```

Mapping rules:

| CMS plan field | Strapi schema field |
| --- | --- |
| `uid` | Component reference value, such as `landing-page.hero` |
| `category` | Component folder under `src/components` |
| `fileName` | Component JSON file name |
| `displayName` | `info.displayName` |
| `fields[]` | `attributes` |

`collectionName` should be generated as:

```text
components_[category_snake_case]_[file_name_snake_case]
```

Example:

```text
landing-page.hero -> components_landing_page_hero
```

## Field Mapping

CMS plan field:

```json
{
  "name": "title",
  "type": "string",
  "required": true
}
```

Strapi attribute:

```json
{
  "title": {
    "type": "string",
    "required": true
  }
}
```

General rule:

```text
FieldPlan.name becomes the attribute key.
All other supported properties become the attribute value.
```

## Field Type Mapping

The table below lists the field types supported by the MVP generator. Strapi supports additional types such as `uid`, `enumeration`, `date`, `datetime`, `relation`, and custom fields, but those can be added later when needed.

| CMS plan type | Strapi attribute type | Notes |
| --- | --- | --- |
| `string` | `string` | Short text |
| `text` | `text` | Long plain text |
| `richtext` | `richtext` | Rich content |
| `boolean` | `boolean` | True/false flags |
| `integer` | `integer` | Whole numbers |
| `decimal` | `decimal` | Decimal numbers |
| `email` | `email` | Email field |
| `json` | `json` | Structured JSON |
| `media` | `media` | Media library field |
| `component` | `component` | Reusable component reference |
| `dynamiczone` | `dynamiczone` | Flexible list of components |

Unsupported or unknown field types should fail validation before file generation.

## Required Fields

CMS plan:

```json
{
  "name": "title",
  "type": "string",
  "required": true
}
```

Strapi attribute:

```json
{
  "title": {
    "type": "string",
    "required": true
  }
}
```

If `required` is false or missing, the generator may omit `required` or set it to `false`. Prefer omitting false values unless a future formatter needs explicit output.

## Media Fields

CMS plan:

```json
{
  "name": "image",
  "type": "media",
  "multiple": false,
  "allowedTypes": ["images"]
}
```

Strapi attribute:

```json
{
  "image": {
    "type": "media",
    "multiple": false,
    "allowedTypes": ["images"]
  }
}
```

Rules:

- `multiple` must be present.
- `allowedTypes` should be present when known.
- For hero images, prefer `multiple: false`.

## Component Fields

CMS plan:

```json
{
  "name": "feature_cards",
  "type": "component",
  "component": "landing-page.feature-card",
  "repeatable": true
}
```

Strapi attribute:

```json
{
  "feature_cards": {
    "type": "component",
    "component": "landing-page.feature-card",
    "repeatable": true
  }
}
```

Rules:

- `component` must reference an existing generated component or known shared component.
- `repeatable` should be explicit.
- Nested repeated cards/items should use repeatable components instead of fixed repeated fields.

## Dynamic Zone Fields

Dynamic zones are not the default MVP output, but the generator should understand the mapping for later use.

CMS plan:

```json
{
  "name": "sections",
  "type": "dynamiczone",
  "components": [
    "landing-page.hero",
    "landing-page.features"
  ]
}
```

Future Strapi attribute:

```json
{
  "sections": {
    "type": "dynamiczone",
    "components": [
      "landing-page.hero",
      "landing-page.features"
    ]
  }
}
```

Note: The current MVP normalizes LLM output into fixed single type attributes such as `hero`, `features`, `pricing`, and `faq`. Dynamic zones can be revisited later when the page builder model becomes more flexible.

## Single Type Attributes Mapping

CMS plan:

```json
{
  "name": "hero",
  "type": "component",
  "component": "landing-page.hero",
  "repeatable": false,
  "sourceSectionIndex": 1
}
```

Strapi content type attribute:

```json
{
  "hero": {
    "type": "component",
    "component": "landing-page.hero",
    "repeatable": false
  }
}
```

`sourceSectionIndex` is useful for review/debugging but should not be written into the Strapi schema file.

## Seed Data Mapping

`seedData` is not schema output.

CMS plan:

```json
{
  "seedData": {
    "hero": {
      "title": "Build beautiful landing pages"
    }
  }
}
```

Future usage:

- content seeding
- preview generation
- sample content import
- migration scripts

The schema generator should ignore `seedData` when writing `schema.json` files.

## Warnings Mapping

`warnings` are not schema output.

They should be preserved for:

- user review
- notebook display
- debug logs
- approval flow in the Java backend later

The schema generator should not write warnings into Strapi schema files.

## Global Blocks Mapping

`globalBlocks` describes how header and footer should be handled.

Example:

```json
{
  "globalBlocks": {
    "header": {
      "handling": "global_single_type",
      "apiName": "global-header",
      "componentPlan": "shared.header"
    },
    "footer": {
      "handling": "global_single_type",
      "apiName": "global-footer",
      "componentPlan": "shared.footer"
    }
  }
}
```

For this MVP, global blocks are not written into the main page schema. Later, the Strapi worker may generate separate single types for global header and footer.

## Generator Guardrails

Before writing files, the future generator should verify:

- every component UID is unique
- every component reference exists
- every field name is snake_case
- every component category and file name is kebab-case
- every media field has `multiple`
- every content type has `kind`, `collectionName`, `info`, `options`, `pluginOptions`, and `attributes`
- `seedData` is not written into schema files
- `warnings` are not written into schema files

## Not Implemented Yet

This step does not:

- generate Strapi files
- create a Strapi project
- install Strapi
- seed content
- restart Strapi

The next implementation step should be a dry-run schema preview that returns generated file paths and JSON content in memory without writing to a real Strapi project.
