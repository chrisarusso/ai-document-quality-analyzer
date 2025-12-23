# Document Quality Analyzer

**Status:** Phase 1 MVP Complete
**Last Updated:** 2025-12-22

## Overview

LLM-powered tool that reviews proposals, kickoffs, and call transcripts before manager review. Analyzes spelling, grammar, formatting, completeness, and ruleset adherence. Posts results to Slack and adds inline comments to Google Docs.

---

## Implementation Status

### What's Working ✅

| Component | Status | Notes |
|-----------|--------|-------|
| **Google Slides extraction** | ✅ Working | Tested with RIF proposal (88 slides) and Sedgwick kickoff (16 slides) |
| **Google Docs extraction** | ✅ Ready | Code complete, not yet tested with real doc |
| **OpenAI analysis** | ✅ Working | GPT-4o-mini for spelling/grammar/content |
| **Scoring system** | ✅ Working | 0-100 score with breakdown by category |
| **Slack notifications** | ✅ Working | Posts to #document-analyzer-test, tags @chris |
| **Google Docs comments** | ✅ Working | Adds unanchored comment with all issues |
| **CLI tool** | ✅ Working | `uv run doc-analyzer analyze URL` |
| **Fathom API connection** | ✅ Connected | API works, 0 meetings in account currently |
| **Rulesets structure** | ✅ Created | JSON files for proposal, kickoff, transcripts |

### What Needs Testing 🧪

| Component | Status | Notes |
|-----------|--------|-------|
| **Anthropic (Claude)** | ⚠️ Needs credits | Account has no balance |
| **Google (Gemini)** | ⚠️ Quota exhausted | Free tier limit reached |
| **Transcript analysis** | 🧪 Untested | BANNT and opportunity/concern detection built but not tested |
| **Google Docs (not Slides)** | 🧪 Untested | Extractor ready, needs real document |
| **Fathom webhook** | 🧪 Untested | Endpoint not yet built |

### Known Issues 🐛

| Issue | Severity | Description |
|-------|----------|-------------|
| **Spacing false positives** | Medium | Slide boundaries create false "spacing errors" when text from slide N runs into slide N+1. LLM sees `"What To Expect\n--- Slide 5 ---"` as spacing issue. |
| **Document type detection** | Low | Auto-detection based on URL only; doesn't detect "kickoff" unless URL contains the word. Use `--type kickoff` to override. |
| **Score variability** | Low | Same document can get different scores on different runs (LLM non-determinism). Consider caching or averaging. |

### Next Steps 📋

**Immediate (to complete Phase 1):**
1. [ ] Build simple webapp (paste URL → see results → post to Slack)
2. [ ] Fix spacing false positives (update prompt to understand slide markers)
3. [ ] Test with a real Google Doc (not Slides)

**Short-term:**
4. [ ] Add Fathom webhook receiver for auto-analysis
5. [ ] Test transcript analysis with real call transcript
6. [ ] Add credits to Anthropic/Google for provider comparison
7. [ ] Tune prompts to reduce false positives

**Future (Phase 2+):**
8. [ ] Store analysis history in database
9. [ ] Track score trends over time
10. [ ] Add custom dictionary UI (click to add term)
11. [ ] Learning from accepted/rejected suggestions

### Test Commands

```bash
cd /Users/chris/web/savas-things/AI/projects/document-quality-analyzer

# Analyze a document
uv run doc-analyzer analyze "GOOGLE_SLIDES_OR_DOCS_URL"

# Analyze with specific type
uv run doc-analyzer analyze "URL" --type kickoff

# Analyze and post to Slack
uv run doc-analyzer analyze "URL" --slack

# Analyze and add comments to document
uv run doc-analyzer analyze "URL" --comment

# Compare all 3 LLM providers (needs credits for Anthropic/Google)
uv run doc-analyzer compare "URL"
```

### Sample Results

**RIF Proposal (88 slides, 47K chars):**
- Score: ~51-63/100 (varies by run)
- Issues: Missing Budget, Timeline, Next Steps sections
- Spacing issues (some false positives from slide boundaries)

**Sedgwick Kickoff (16 slides, 5K chars):**
- Score: ~47-63/100 (varies by run)
- Issues: Missing Executive Summary, Budget
- Real grammar error found: "the those phases"

---

## Phase 1 Specification

### Document Types (Phase 1)

| Type | Format | Input Method | Trigger |
|------|--------|--------------|---------|
| **Proposals** | Google Docs or Slides | URL via webapp | Manual |
| **Client Kickoffs** | Google Slides | URL via webapp | Manual |
| **Call Transcripts** | URL (Fathom) or text file | Webhook or URL | Automatic (webhook) or Manual |

### Quality Checks

#### All Document Types

| Check | Affects Score | Notes |
|-------|---------------|-------|
| Spelling errors | ✅ Yes | Strict, with learnable custom dictionary |
| Grammar issues | ✅ Yes | Context-aware (their/there/they're) |
| Spacing (double spaces, missing) | ✅ Yes | |
| Formatting consistency | ⚠️ Flag only | Bullet styles, heading hierarchy |
| Math verification (tables) | ✅ Yes | For proposals with budgets/numbers |
| Required content (per ruleset) | ✅ Yes | Different rules per document type |
| Style issues (passive voice, jargon) | ⚠️ Flag only | Subjective, not scored |

#### Proposal-Specific Checks

- Custom required mentions per proposal (configurable)
- Budget/pricing table math validation
- Scope clarity
- Deliverables defined

#### Client Kickoff-Specific Checks

- Must mention "risk" (default ruleset)
- Project timeline present
- Stakeholders identified
- Success criteria defined

#### Call Transcript Analysis

**Sales Calls - BANNT Scoring:**
| Element | What to Check |
|---------|---------------|
| **B**udget | Was budget discussed? Range identified? |
| **A**uthority | Decision maker identified? Who has authority? |
| **N**eed | Pain points articulated? Problem clearly stated? |
| **N**ext Steps | Follow-up scheduled? Clear action items? |
| **T**imeline | Timeline discussed? Urgency level? |

**Client Calls - Opportunity/Risk Detection:**
| Signal Type | What to Detect |
|-------------|----------------|
| **Opportunities** | Additional work outside scope, referrals, expansion mentions |
| **Concerns - Functionality** | Feature complaints, usability issues, missing capabilities |
| **Concerns - Satisfaction** | Frustration, disappointment, unmet expectations |
| **Concerns - Schedule** | Timeline worries, delays mentioned, deadline pressure |
| **Concerns - Budget** | Cost concerns, budget constraints, pricing pushback |

### Rulesets

```
rulesets/
├── default.json              # Base rules for all documents
├── proposal.json             # Proposal-specific rules
├── kickoff.json              # Kickoff-specific rules
├── transcript-sales.json     # Sales call BANNT rules
└── transcript-client.json    # Client call opportunity/risk rules
```

Each ruleset defines:
- Required keywords/phrases
- Forbidden patterns (if any)
- Section requirements
- Scoring weights

Rulesets are extensible - easy to add new rules over time.

### Custom Dictionary

Learnable dictionary for terms that shouldn't be flagged:
- Technical terms (Drupal, Kubernetes, etc.)
- Brand names
- Client-specific terminology
- Industry jargon

**UI Goal:** Click a flagged term to add to dictionary (Phase 1 stretch)

### Scoring System

**Numeric score (0-100)** with breakdown:

```
Overall Score: 87/100

Breakdown:
- Spelling/Grammar/Spacing: 45/50 (3 issues found)
- Required Content: 35/40 (1 missing section)
- Math Accuracy: 7/10 (1 calculation error)

Flagged (not scored):
- 2 passive voice instances
- 1 potential jargon term
```

**For call transcripts (BANNT):**
```
BANNT Score: 4/5

✅ Budget: Discussed ($50-75K range)
✅ Authority: CEO identified as decision maker
✅ Need: Clear pain point (manual processes)
⚠️ Next Steps: No follow-up scheduled
✅ Timeline: Q1 2025 target
```

### Output Channels

#### 1. Slack Notifications

All analyses post to designated Slack channel, tagging @chris:

```
📄 Document Analysis Complete

Document: Q1 Proposal - Acme Corp
Type: Proposal
Score: 87/100
Link: [Google Doc URL]

Issues Found:
• 🔴 Spelling: "recieve" → "receive" (line 45)
• 🔴 Math: Budget total shows $52,000 but items sum to $54,500
• 🟡 Missing: Risk section not found
• ⚪ Style: Consider active voice (line 23)

[View Full Report]
```

#### 2. Google Docs Comments

Unanchored comments added via Drive API:

```
[Document Quality Analyzer]

Line 45: Spelling error
"recieve" should be "receive"

---

Line 72: Math discrepancy
Budget total shows $52,000 but line items sum to $54,500.
Suggested fix: Update total to $54,500 or verify line items.
```

### User Workflows

#### Manual Document Analysis
1. User pastes Google Doc/Slides URL into webapp
2. System fetches document via OAuth
3. LLM analyzes against appropriate ruleset
4. Results posted to Slack + comments added to Doc
5. User fixes issues
6. User can re-run to see improvement

#### Automatic Call Transcript Analysis
1. Fathom webhook fires when recording completes
2. System fetches transcript
3. Analyzes against BANNT or client-call ruleset
4. Results posted to Slack with @chris tag
5. Opportunities/concerns highlighted for action

### Technical Architecture

#### Dual Implementation (Compare Both)

**Option A: Google Apps Script**
- Native Google Docs/Slides integration
- Runs in Google Cloud (free)
- Limited but familiar
- Reuse patterns from `proposal-submission-workflow`

**Option B: Python + FastAPI**
- More powerful NLP capabilities
- Easier LLM integration
- Requires hosting
- Better for webhook handling

**Phase 1 Goal:** Build both, compare results, choose winner.

#### LLM Comparison

Run same analysis with all 3, compare output quality:

| Provider | Model | Cost (est.) |
|----------|-------|-------------|
| OpenAI | GPT-4o-mini | $0.15/1M input |
| Anthropic | Claude 3.5 Haiku | $0.25/1M input |
| Google | Gemini 1.5 Flash | $0.075/1M input |

#### Authentication

- **Google OAuth** for Docs/Slides access
- User authorizes app once
- Refresh tokens stored securely

#### Storage

Cloud database (PostgreSQL or similar):
- Analysis history per document
- Score trends over time
- Custom dictionary entries
- Ruleset configurations

Tracking improvements over time for marketing purposes.

### Data Model

```sql
-- Documents analyzed
documents (
  id, url, type, title,
  first_analyzed_at, last_analyzed_at
)

-- Analysis runs
analyses (
  id, document_id,
  score, breakdown_json,
  issues_json, llm_provider,
  created_at
)

-- Custom dictionary
dictionary (
  id, term, added_by, added_at
)

-- Rulesets
rulesets (
  id, name, type, rules_json,
  is_default, created_at
)
```

### API Endpoints

```
POST /analyze
  body: { url: "https://docs.google.com/...", type: "proposal" }
  returns: { score, issues, slack_message_url }

POST /webhook/fathom
  body: { transcript_url, meeting_title, attendees }
  returns: { received: true }

GET /history/{document_id}
  returns: [{ score, date, issues_count }, ...]

POST /dictionary
  body: { term: "Drupal" }
  returns: { added: true }

GET /rulesets
  returns: [{ name, type, rules }, ...]

PUT /rulesets/{id}
  body: { rules_json }
  returns: { updated: true }
```

### Phase 1 Deliverables

| Deliverable | Priority | Status |
|-------------|----------|--------|
| Google Docs/Slides text extraction | P0 | ✅ Done |
| LLM analysis (spelling/grammar/content) | P0 | ✅ Done |
| Ruleset system (default + per-type) | P0 | ✅ Done |
| Slack notification posting | P0 | ✅ Done |
| Google Docs comment insertion | P0 | ✅ Done |
| Numeric scoring system | P0 | ✅ Done |
| Simple webapp (paste URL) | P0 | ⬜ Not started |
| BANNT scoring for sales calls | P1 | 🔶 Built, untested |
| Opportunity/concern detection for client calls | P1 | 🔶 Built, untested |
| Fathom webhook receiver | P1 | ⬜ Not started |
| Compare 3 LLM providers | P1 | 🔶 Partial (OpenAI works, others need credits) |
| Analysis history storage | P2 | ⬜ Not started |
| Score trend tracking | P2 | ⬜ Not started |
| Custom dictionary (add terms) | P2 | ⬜ Not started |

### Out of Scope (Phase 1)

- ❌ Auto-fix (only suggest)
- ❌ Learning from feedback
- ❌ Manager dashboard
- ❌ Template order enforcement
- ❌ PDF export

---

## Phase 2+ (Future)

**Phase 2:**
- Learning from accepted/rejected suggestions
- Template comparison and strict adherence
- Clickable "add to dictionary" in reports

**Phase 3:**
- Manager dashboard with team quality metrics
- Integration with multi-source knowledge base
- Suggested content from past proposals

---

## Success Metrics

- Review cycles: Reduce from 3 → 1.5 iterations
- Manager time: Save 30 min per document
- Quality score: Track improvement over time (for marketing)
- Adoption: Team uses before submission
- False positives: Easy to dismiss unhelpful suggestions

## Related Work

- `proposal-submission-workflow/`: LLM patterns, Google Docs integration, audit logging
- `website-quality-agent/`: Scoring algorithms, issue categorization, report generation
- `multi-source-knowledge-base/`: Could provide context for suggestions

## Open Questions (Resolved)

- [x] What are the top 10 issues? → Spelling, grammar, spacing, math, missing content
- [x] What sections are required? → Defined per ruleset
- [x] How to handle client-specific customizations? → Global custom dictionary
- [x] Should it enforce or just suggest? → Suggest with scores, flag subjective issues
- [x] Google Docs comments feasible? → Yes, unanchored via Drive API

## Next Steps

~~1. Set up project structure (Python + Apps Script)~~ ✅
~~2. Implement Google Docs/Slides text extraction~~ ✅
~~3. Create base ruleset structure~~ ✅
~~4. Build LLM analysis with all 3 providers~~ ✅
~~5. Add Slack integration~~ ✅
~~6. Add Google Docs comment insertion~~ ✅
7. Build simple webapp ⬜
~~8. Test with real proposal document~~ ✅

See **Implementation Status** section above for detailed next steps.
