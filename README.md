# Strapi CMS Agent

Strapi CMS Agent is an Agentic AI monorepo for converting uploaded or pasted HTML webpages into automatically configured Strapi CMS projects.

The application analyzes webpage structure, proposes a validated Strapi schema plan, lets the user review and approve it, and then applies the approved schema to a generated Strapi CMS instance.

## Main Services

- `web`: Next.js web application for chat, HTML upload, schema preview, and approval flows.
- `backend`: Java backend control plane for projects, uploads, conversations, approvals, jobs, and orchestration.
- `ai-agent`: Python AI agent service for HTML analysis and Strapi schema planning.
- `strapi-worker`: Node.js worker for Strapi project setup, schema file generation, and runtime automation.

## Basic Architecture Flow

User -> Web App -> Java Backend -> Python AI Agent -> Node Strapi Worker -> Strapi CMS
