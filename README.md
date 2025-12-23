# Document Quality Analyzer

LLM-powered document review tool for proposals, kickoffs, and call transcripts.

## Features

- Analyzes Google Docs and Slides for spelling, grammar, and content issues
- Scores documents against configurable rulesets
- Analyzes call transcripts for BANNT scoring (sales) and opportunity/concern detection (client calls)
- Posts results to Slack with inline Google Docs comments

## Quick Start

```bash
# Install dependencies
uv sync

# Run analysis on a document
uv run doc-analyzer analyze https://docs.google.com/...

# Start the web server
uv run uvicorn doc_analyzer.api:app --reload

# Open the UI (after server starts)
# http://localhost:8000
```

## Web UI (Phase 1)

- Visit `http://localhost:8000`
- Paste a Google Doc/Slides URL
- Choose provider (OpenAI/Anthropic/Google)
- Optional toggles: post to Slack, add Google Doc/Slides comment
- Shows score, issues count, and raw JSON response

## Configuration

Copy `env.example` to `.env` and configure:

- `FATHOM_API_KEY` - For call transcript access
- `OPENAI_API_KEY` - For LLM analysis
- `SLACK_BOT_TOKEN` - For posting results
