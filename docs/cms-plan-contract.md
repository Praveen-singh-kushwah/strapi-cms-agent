# CMS Plan Contract

This document defines the canonical CMS plan shape that the AI agent should produce before any Strapi schema files are generated.

The goal is to keep LLM output, deterministic fallback output, validation, and future schema generation aligned.

## Why This Contract Exists

LLMs can produce many valid-looking schema plans for the same page. For example, a hero CTA might be modeled as:

```json
{
  "primary_cta_label": "View plans",
  "primary_cta_href": "#pricing"
}
```

or as:

```json
{
  "primary_cta": {
    "text": "View plans",
    "url": "#pricing"
  }
}
```

Both are understandable, but the generator needs one canonical contract. This document defines that contract.

## Top-Level Shape

The canonical CMS plan must use this top-level shape:

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

## Canonical Single Type Attributes

For the landing page MVP, the page single type should use these attributes when the matching sections are detected:

```text
seo
hero
features
testimonials
pricing
faq
contact
```

The section attributes should be non-repeatable component fields.

Example:

```json
{
  "name": "hero",
  "type": "component",
  "component": "landing-page.hero",
  "repeatable": false,
  "sourceSectionIndex": 1
}
```

Avoid generic attributes such as:

```text
title
description
sections
hero_section
features_section
```

If an LLM returns those, the planner should normalize them into the canonical names above.

## Shared Components

The MVP assumes these shared components may exist or be generated later:

```text
shared.seo
shared.link
shared.text-item
```

`shared.link` is the canonical shape for CTA/link fields:

```json
{
  "text": "View plans",
  "url": "#pricing"
}
```

## Hero Section

Canonical component UID:

```text
landing-page.hero
```

Canonical fields:

```json
[
  {
    "name": "eyebrow",
    "type": "string",
    "required": false
  },
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "primary_cta",
    "type": "component",
    "component": "shared.link",
    "repeatable": false
  },
  {
    "name": "secondary_cta",
    "type": "component",
    "component": "shared.link",
    "repeatable": false
  },
  {
    "name": "image",
    "type": "media",
    "multiple": false,
    "allowedTypes": ["images"]
  }
]
```

Avoid split CTA fields such as:

```text
primary_cta_label
primary_cta_href
secondary_cta_label
secondary_cta_href
```

Those should be normalized to `primary_cta` and `secondary_cta`.

Canonical seed data:

```json
{
  "hero": {
    "eyebrow": "Launch faster with less busywork",
    "title": "Build beautiful landing pages without rebuilding your CMS",
    "description": "LaunchFlow helps teams publish campaigns, capture leads, and manage content from one simple workspace.",
    "primary_cta": {
      "text": "View plans",
      "url": "#pricing"
    },
    "secondary_cta": {
      "text": "Explore features",
      "url": "#features"
    },
    "image": {
      "src": "images/dashboard-preview.png",
      "alt": "LaunchFlow dashboard preview"
    }
  }
}
```

## Features Section

Canonical section component UID:

```text
landing-page.features
```

Canonical nested item component UID:

```text
landing-page.feature-card
```

Canonical section fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "items",
    "type": "component",
    "component": "landing-page.feature-card",
    "repeatable": true
  }
]
```

Acceptable LLM variants such as `feature_cards`, `cards`, or `feature_items` should be normalized to `items`.

Canonical feature card fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  }
]
```

## Testimonials Section

Canonical section component UID:

```text
landing-page.testimonials
```

Canonical nested item component UID:

```text
landing-page.testimonial-card
```

Canonical section fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "items",
    "type": "component",
    "component": "landing-page.testimonial-card",
    "repeatable": true
  }
]
```

Canonical testimonial card fields:

```json
[
  {
    "name": "quote",
    "type": "text",
    "required": true
  },
  {
    "name": "author_name",
    "type": "string",
    "required": false
  },
  {
    "name": "author_role",
    "type": "string",
    "required": false
  }
]
```

## Pricing Section

Canonical section component UID:

```text
landing-page.pricing
```

Canonical nested item component UIDs:

```text
landing-page.pricing-card
landing-page.pricing-feature
```

Canonical section fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "items",
    "type": "component",
    "component": "landing-page.pricing-card",
    "repeatable": true
  }
]
```

Canonical pricing card fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "price",
    "type": "string",
    "required": false
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "features",
    "type": "component",
    "component": "landing-page.pricing-feature",
    "repeatable": true
  },
  {
    "name": "is_highlighted",
    "type": "boolean",
    "required": false
  }
]
```

Avoid repeatable scalar fields such as:

```json
{
  "name": "features",
  "type": "text",
  "repeatable": true
}
```

Those should be normalized to the `landing-page.pricing-feature` component.

Canonical pricing feature fields:

```json
[
  {
    "name": "text",
    "type": "string",
    "required": true
  }
]
```

## FAQ Section

Canonical section component UID:

```text
landing-page.faq
```

Canonical nested item component UID:

```text
landing-page.faq-item
```

Canonical section fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "items",
    "type": "component",
    "component": "landing-page.faq-item",
    "repeatable": true
  }
]
```

Canonical FAQ item fields:

```json
[
  {
    "name": "question",
    "type": "string",
    "required": true
  },
  {
    "name": "answer",
    "type": "text",
    "required": true
  }
]
```

## Contact Section

Canonical section component UID:

```text
landing-page.contact
```

Canonical nested item component UIDs:

```text
landing-page.form-config
landing-page.form-field
```

Canonical section fields:

```json
[
  {
    "name": "title",
    "type": "string",
    "required": true
  },
  {
    "name": "description",
    "type": "text",
    "required": false
  },
  {
    "name": "form",
    "type": "component",
    "component": "landing-page.form-config",
    "repeatable": false
  }
]
```

Canonical form config fields:

```json
[
  {
    "name": "action",
    "type": "string",
    "required": false
  },
  {
    "name": "method",
    "type": "string",
    "required": false
  },
  {
    "name": "submit_label",
    "type": "string",
    "required": false
  },
  {
    "name": "fields",
    "type": "component",
    "component": "landing-page.form-field",
    "repeatable": true
  }
]
```

Canonical form field fields:

```json
[
  {
    "name": "label",
    "type": "string",
    "required": false
  },
  {
    "name": "name",
    "type": "string",
    "required": true
  },
  {
    "name": "input_type",
    "type": "string",
    "required": false
  },
  {
    "name": "required",
    "type": "boolean",
    "required": false
  }
]
```

Avoid flattened fields such as:

```text
form_action
form_method
submit_label
```

Those should be normalized into a nested `form` component.

## Normalization Responsibilities

The planner should normalize common LLM variants before validation:

| LLM variant | Canonical form |
| --- | --- |
| `hero_section` | `hero` |
| `features_section` | `features` |
| `title`, `description`, `sections` | section attributes such as `hero`, `features`, `pricing` |
| `primary_cta_label` + `primary_cta_href` | `primary_cta` component |
| `secondary_cta_label` + `secondary_cta_href` | `secondary_cta` component |
| `feature_cards`, `feature_items`, `cards` | `items` |
| `testimonial_cards`, `testimonial_items` | `items` |
| `pricing_cards`, `pricing_items` | `items` |
| `faq_items` | `items` |
| repeatable scalar pricing `features` | repeatable `landing-page.pricing-feature` component |
| `form_action`, `form_method`, `submit_label` | nested `form` component |

## Validation Responsibilities

The validator should report errors when:

- component UIDs are invalid
- component references are missing or unknown
- single type attributes do not match seed data keys
- required top-level CMS plan keys are missing
- field names are not snake_case

The validator should report warnings when:

- media fields do not define `multiple`
- pricing features are still repeatable scalar fields
- contact form fields are flattened instead of componentized
- shared components are referenced but not included in the plan

## Not Implemented Yet

This contract does not generate Strapi files. It defines the canonical plan shape that later generator code should consume.
