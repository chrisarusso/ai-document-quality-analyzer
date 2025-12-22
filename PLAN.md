# Document Quality Analyzer

**Status:** Planning
**Last Updated:** 2025-12-21

## Overview

LLM-powered tool that reviews proposals, kickoffs, task orders, and other business documents before manager review. Checks spelling, grammar, formatting, completeness, and adherence to templates.

## AI Readiness Categories Coverage

- ✅ Generative AI
- ✅ Agents, Assistants & Automation
- ✅ Training & Empowerment
- ✅ Data & Engineering
- ✅ Product Strategy
- ⚠️ Privacy, Security & Compliance (document confidentiality)
- ❌ Search & Content Discoverability
- ❌ Personalization

## Document Types

### Proposals
- Strategic proposals (RFPs)
- Task orders
- Statements of work

### Project Documents
- Kickoff documents (Lu)
- Build documents (Zakk)
- Technical specifications

### Business Documents
- Contracts
- Terms & conditions
- Client communications

## Quality Checks

### Basic Quality
- Spelling errors
- Grammar issues
- Spacing inconsistencies (double spaces, missing spaces)
- Formatting consistency
- Word choice (avoid jargon, unclear terms)

### Template Adherence
- All required sections present
- Sections in correct order
- Standard clauses included
- Proper header/footer
- Version numbering

### Content Quality
- Clear scope definition
- Measurable deliverables
- Realistic timelines
- Complete acceptance criteria
- Risk identification

### Style Guide
- Consistent terminology
- Active voice preferred
- Clear, concise language
- Proper use of technical terms
- Brand voice alignment

## Technical Architecture

### Document Ingestion
- Support: .docx, .pdf, Google Docs
- Preserve formatting for context
- Extract metadata (author, date, version)

### Analysis Engine
- **LLM for content quality**: GPT-4 for reasoning about clarity, completeness
- **Deterministic checks**: Spelling, grammar (LanguageTool), spacing
- **Template matching**: Compare against standard templates
- **Diff generation**: Highlight changes from template

### Feedback System
- Inline comments (Google Docs style)
- Severity levels: Critical, High, Medium, Low, Suggestion
- Explanations: Why each issue matters
- Suggested fixes: Not just "wrong" but "try this instead"

### Learning System
- Track which suggestions get accepted
- Learn from manager edits
- Improve template matching over time

## Workflow Integration

### For Writers (Lu, Zakk, team)
1. Draft document
2. Run through analyzer before submitting
3. Review feedback, make corrections
4. Resubmit to analyzer (optional)
5. Send to manager for final review

### For Managers
1. Receive pre-checked document
2. Focus on strategy, not typos
3. Track quality improvements over time

## MVP Scope

**Phase 1 (1 week)**
- Basic spelling/grammar/spacing checks
- PDF report with issues highlighted
- CLI tool for local use

**Phase 2 (1 week)**
- Template comparison for proposals
- Completeness checking (required sections)
- Suggested fixes, not just detection

**Phase 3 (2 weeks)**
- Google Docs integration (inline comments)
- Learning from accepted/rejected suggestions
- Manager dashboard (team quality metrics)

## Success Metrics

- Review cycles: Reduce from 3 → 1.5 iterations
- Manager time: Save 30 min per document
- Quality score: Increase from 75% → 90% on first submission
- Adoption: 80%+ of team using before submission
- False positives: <10% of suggestions rejected

## Proof Points

- `proposal-submission-workflow/` directory exists with prior work
- Common issues: spelling, spacing, grammar already identified
- Templates exist for proposals and task orders

## Open Questions

- [ ] What are the top 10 issues Lu and Zakk find in reviews?
- [ ] What sections are required for each document type?
- [ ] How to handle client-specific customizations?
- [ ] Should it enforce or just suggest?
- [ ] How to prevent over-reliance on automation?

## Related Work

- Google Drive T&C organizer: Document processing patterns
- Template generator service: Template extraction/matching
- Multi-source knowledge base: Could suggest relevant past work

## Next Steps

- [ ] Interview Lu and Zakk about common review issues
- [ ] Collect 10 examples each: proposals, kickoffs, builds
- [ ] Extract template from existing documents
- [ ] Create scoring rubric (what makes a "good" document?)
- [ ] Build prototype with 1 document type (proposals)
