# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AI-powered projects for Savas Labs. Contains internal tools, client demos, and three new projects in planning phase.

## Project Structure

```
projects/
├── karpathy-llm-council/   # 3-stage LLM deliberation system (Python/FastAPI + React/Vite)
├── savas/
│   ├── shared/             # Active tools (MCP server, proposal workflow, RIF demo)
│   └── not/                # Completed (Secret Savas RAG - 700K messages)
├── document-quality-analyzer/    # PLANNING - Pre-review proposals/kickoffs
├── multi-source-knowledge-base/  # PLANNING - Unified search (Slack/Drive/GitHub)
└── website-quality-agent/        # PLANNING - Crawl/fix website quality issues
```

## Commands

### karpathy-llm-council
```bash
# Backend (Python + FastAPI) - runs on port 8001 NOT 8000
cd projects/karpathy-llm-council/llm-council/backend
uv sync
uvicorn main:app --port 8001

# Frontend (React + Vite) - port 5173
cd projects/karpathy-llm-council/llm-council/frontend
npm install && npm run dev
npm run lint
```

### savas/shared/mcp-server (TypeScript)
```bash
npm run build      # TypeScript compilation
npm run dev        # Development server
npm run pm2:start  # Production deployment
```

### savas/shared/proposal-submission-workflow (Google Apps Script)
```bash
npm run clasp:login  # Auth with Google
npm run clasp:push   # Deploy to Apps Script
```

## Tech Stack

- **PostgreSQL + pgvector** for vector search (RAG projects)
- **Google APIs** (Drive, Sheets, Slides, Calendar)

## Code Patterns

### Python imports - use relative imports in backend modules
```python
from .config import COUNCIL_MODELS
from .openrouter import query_models_parallel
```

### Async parallel LLM queries
```python
results = await asyncio.gather(*tasks, return_exceptions=True)
```

## Development Standards

### Code Comments
Write clear comments explaining the "why" not just the "what". Each function should have a docstring explaining its purpose, parameters, and return value. Complex logic blocks need inline comments.

### Testing First
Write tests early, before the code is complex. Start with basic smoke tests to catch obvious errors. This saves debugging time later. Run tests after each significant change.

### Documentation
Prefer fewer, longer markdown files over many small ones. Consolidate related information. Each project needs at most: README.md (if public-facing), PLAN.md (for planning phase), CLAUDE.md (if project-specific overrides needed).

### Error Handling
Fail fast with clear error messages during development. Log enough context to debug issues. Don't silently swallow exceptions.

### Dependencies
Discuss before adding new dependencies. Prefer well-maintained, minimal libraries. Pin versions in requirements files.

### Code Organization
Keep files focused - if a file exceeds ~300 lines, consider splitting. New files go in existing directories, not at project root. Delete unused code rather than commenting it out.

### When to Ask
Ask before: major architectural decisions, adding dependencies, changing shared code. Proceed without asking: bug fixes, tests, refactoring within a single file.

## Environment

- `.env` files ARE tracked (non-production learning projects)
- API keys: OpenAI, Google, Slack, Anthropic

## Planning Documents

Each new project has a PLAN.md with scope, architecture, and success metrics:
- @./projects/document-quality-analyzer/PLAN.md
- @./projects/multi-source-knowledge-base/PLAN.md
- @./projects/website-quality-agent/PLAN.md

Ideas tracker: @./AI-IDEAS.md
