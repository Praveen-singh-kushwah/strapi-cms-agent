# Architecture

Strapi CMS Agent is organized as a monorepo with separate services for the web interface, backend control plane, AI analysis, and Strapi automation.

## Service Responsibilities

- `apps/web`: User interface for chat, HTML upload, schema plan review, and approvals.
- `apps/backend`: Java control plane for users, projects, uploads, conversations, jobs, schema plans, approvals, and orchestration.
- `apps/ai-agent`: Python service for sanitizing HTML, parsing page structure, detecting sections, and generating validated Strapi schema plans.
- `apps/strapi-worker`: Node.js worker for generating Strapi schema files, applying approved plans, restarting Strapi, and reporting results.
- `packages/shared-types`: Shared type definitions and validation contracts.
- `packages/prompts`: Prompt templates for AI workflows.
- `infra`: Local infrastructure, Docker configuration, and operational scripts.

## Flow

User -> Web App -> Java Backend -> Python AI Agent -> Java Backend -> Node Strapi Worker -> Strapi CMS

The AI service creates a schema plan first. The backend stores the plan and requires user approval before the Strapi worker applies changes to a Strapi project.
