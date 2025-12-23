"""FastAPI webapp for the Document Quality Analyzer."""

import logging
from typing import Optional, Literal
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl

from .analyzers.quality_analyzer import QualityAnalyzer
from .integrations.fathom import FathomClient
from .integrations.slack import SlackNotifier
from .models import AnalysisResult, DocumentType, Issue

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Document Quality Analyzer",
    version="0.1.0",
    description="Paste a Google Doc/Slides URL to analyze quality, score it, and optionally post to Slack.",
)


class AnalyzeRequest(BaseModel):
    """Request payload for /api/analyze."""

    url: HttpUrl
    provider: Literal["openai", "anthropic", "google"] = "openai"
    type: Optional[DocumentType] = None
    slack: bool = False
    comment: bool = False


class AnalyzeResponse(BaseModel):
    """Response payload for /api/analyze."""

    analysis: dict
    slack: Optional[dict] = None
    comment: Optional[dict] = None


class AnalyzeFathomRequest(BaseModel):
    """Request payload for /api/analyze-fathom."""

    recording_id: str
    provider: Literal["openai", "anthropic", "google"] = "openai"
    is_sales_call: bool = True
    slack: bool = False


class AnalyzeFathomResponse(BaseModel):
    """Response payload for /api/analyze-fathom."""

    analysis: dict
    fathom: dict
    slack: Optional[dict] = None


# --- Fathom Webhook Models ---


class FathomSpeaker(BaseModel):
    """Speaker in a transcript entry."""

    display_name: str
    matched_calendar_invitee_email: Optional[str] = None


class FathomTranscriptEntry(BaseModel):
    """Single transcript entry from Fathom webhook."""

    speaker: FathomSpeaker
    text: str
    timestamp: str


class FathomSummary(BaseModel):
    """Summary object from Fathom webhook."""

    template_name: Optional[str] = None
    markdown_formatted: Optional[str] = None


class FathomCalendarInvitee(BaseModel):
    """Calendar invitee from Fathom webhook."""

    name: Optional[str] = None
    email: Optional[str] = None
    is_external: Optional[bool] = None


class FathomWebhookPayload(BaseModel):
    """Payload sent by Fathom when a recording is ready.

    See: https://developers.fathom.ai/api-reference/webhook-payloads/new-meeting-content-ready
    """

    recording_id: int
    title: str
    meeting_title: Optional[str] = None
    url: Optional[str] = None
    share_url: Optional[str] = None
    created_at: Optional[str] = None
    calendar_invitees_domains_type: Optional[str] = None  # "only_internal" or "one_or_more_external"
    transcript: Optional[list[FathomTranscriptEntry]] = None
    default_summary: Optional[FathomSummary] = None
    action_items: Optional[list[dict]] = None
    calendar_invitees: Optional[list[FathomCalendarInvitee]] = None

    def get_full_transcript_text(self) -> str:
        """Combine all transcript entries into a single text block."""
        if not self.transcript:
            return ""
        lines = []
        for entry in self.transcript:
            lines.append(f"[{entry.timestamp}] {entry.speaker.display_name}: {entry.text}")
        return "\n".join(lines)

    def get_attendee_summary(self) -> str:
        """Get a brief summary of attendees."""
        if not self.calendar_invitees:
            return "Unknown attendees"
        names = [inv.name or inv.email or "Unknown" for inv in self.calendar_invitees[:5]]
        if len(self.calendar_invitees) > 5:
            names.append(f"+{len(self.calendar_invitees) - 5} more")
        return ", ".join(names)


def _serialize_issue(issue: Issue) -> dict:
    """Convert Issue model to JSON-serializable dict."""
    return {
        "category": issue.category.value,
        "severity": issue.severity.value,
        "title": issue.title,
        "description": issue.description,
        "location": issue.location,
        "context": issue.context,
        "suggestion": issue.suggestion,
        "affects_score": issue.affects_score,
    }


def _serialize_result(result: AnalysisResult) -> dict:
    """Convert AnalysisResult model to JSON-serializable dict."""
    score = result.score.dict() | {"overall": result.score.overall} if result.score else None
    bannt = result.bannt_score.dict() | {"score": result.bannt_score.score} if result.bannt_score else None

    return {
        "document_url": result.document_url,
        "document_title": result.document_title,
        "document_type": result.document_type.value,
        "analyzed_at": result.analyzed_at.isoformat(),
        "llm_provider": result.llm_provider,
        "score": score,
        "bannt_score": bannt,
        "issues": [_serialize_issue(i) for i in result.issues],
        "text_length": result.text_length,
    }


def _build_comment(analyzer: QualityAnalyzer, url: str, result: AnalysisResult) -> dict:
    """Add a single comment summarizing issues to the document."""
    extractor = analyzer.slides_extractor if "/presentation/" in url else analyzer.docs_extractor

    comment_lines = ["[Document Quality Analyzer]", ""]

    for issue in result.issues[:20]:
        line = f"{issue.severity.value.upper()} {issue.category.value}: {issue.title}"
        if issue.location:
            line += f" ({issue.location})"
        comment_lines.append(line)

        if issue.suggestion:
            comment_lines.append(f"   → {issue.suggestion}")
        comment_lines.append("")

    if len(result.issues) > 20:
        comment_lines.append(f"... and {len(result.issues) - 20} more issues")

    return extractor.add_comment(url, "\n".join(comment_lines))


def _fetch_fathom_transcript(recording_id: str) -> dict:
    """Fetch a Fathom transcript and return a JSON-serializable dict."""
    client = FathomClient()
    # Fathom client is async; run in a sync context via asyncio in threadpool.
    import asyncio

    transcript = asyncio.run(client.get_transcript(recording_id))
    return {
        "recording_id": transcript.recording_id,
        "title": transcript.title,
        "url": transcript.url,
        "share_url": transcript.share_url,
        "created_at": transcript.created_at.isoformat(),
        "summary": transcript.summary,
        "action_items": transcript.action_items,
        "text_length": len(transcript.full_text),
    }, transcript.full_text, transcript.title, (transcript.share_url or transcript.url or "transcript")


@app.get("/health")
async def health() -> dict:
    """Simple health check."""
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze a Google Doc/Slides URL and optionally post to Slack or add comments."""
    analyzer = QualityAnalyzer(provider=request.provider)

    try:
        result = await run_in_threadpool(analyzer.analyze_url, str(request.url), request.type)
    except Exception as exc:  # pragma: no cover - defensive user facing error
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slack_result = None
    if request.slack:
        notifier = SlackNotifier()
        slack_result = await run_in_threadpool(notifier.post_analysis, result)

    comment_result = None
    if request.comment:
        comment_result = await run_in_threadpool(_build_comment, analyzer, str(request.url), result)

    return {
        "analysis": _serialize_result(result),
        "slack": slack_result,
        "comment": comment_result,
    }


@app.post("/api/analyze-fathom", response_model=AnalyzeFathomResponse)
async def analyze_fathom(request: AnalyzeFathomRequest):
    """Fetch a Fathom transcript by recording_id and analyze it."""
    analyzer = QualityAnalyzer(provider=request.provider)

    try:
        fathom_meta, transcript_text, title, url = await run_in_threadpool(
            _fetch_fathom_transcript, request.recording_id
        )
        result = await run_in_threadpool(
            analyzer.analyze_transcript,
            transcript_text,
            request.is_sales_call,
            title,
        )
        # Make the result link point to the Fathom recording/share URL when available.
        result.document_url = url
    except Exception as exc:  # pragma: no cover - defensive user facing error
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slack_result = None
    if request.slack:
        notifier = SlackNotifier()
        slack_result = await run_in_threadpool(notifier.post_analysis, result)

    return {
        "analysis": _serialize_result(result),
        "fathom": fathom_meta,
        "slack": slack_result,
    }


def _post_fathom_webhook_to_slack(payload: FathomWebhookPayload) -> dict:
    """Post a simple notification about a new Fathom recording to Slack.

    This is the POC version - just posts meeting info, no analysis yet.
    """
    notifier = SlackNotifier()

    # Build a simple Slack message
    meeting_link = payload.share_url or payload.url or "No link available"
    attendees = payload.get_attendee_summary()
    call_type = "External" if payload.calendar_invitees_domains_type == "one_or_more_external" else "Internal"

    # Get summary if available
    summary_text = ""
    if payload.default_summary and payload.default_summary.markdown_formatted:
        # Truncate summary to first 500 chars
        summary = payload.default_summary.markdown_formatted[:500]
        if len(payload.default_summary.markdown_formatted) > 500:
            summary += "..."
        summary_text = f"\n\n*Summary:*\n{summary}"

    # Get action items if available
    action_items_text = ""
    if payload.action_items:
        items = [f"• {item.get('description', 'Unknown')}" for item in payload.action_items[:5]]
        if items:
            action_items_text = f"\n\n*Action Items:*\n" + "\n".join(items)
            if len(payload.action_items) > 5:
                action_items_text += f"\n_+{len(payload.action_items) - 5} more_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "New Fathom Recording"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Meeting:*\n{payload.title}"},
                {"type": "mrkdwn", "text": f"*Type:*\n{call_type}"},
            ]
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Attendees:*\n{attendees}"},
                {"type": "mrkdwn", "text": f"*Recording ID:*\n{payload.recording_id}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<{meeting_link}|View Recording>"}
        },
    ]

    # Add summary block if available
    if summary_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary_text}
        })

    # Add action items block if available
    if action_items_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": action_items_text}
        })

    # Add mention
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "cc @chris"}]
    })

    if not notifier.client:
        # Dry run
        logger.info(f"[DRY RUN] Would post Fathom webhook to Slack: {payload.title}")
        return {"success": True, "dry_run": True}

    try:
        response = notifier.client.chat_postMessage(
            channel=notifier.channel,
            blocks=blocks,
            text=f"New Fathom Recording: {payload.title}",
        )
        return {
            "success": True,
            "channel": response["channel"],
            "ts": response["ts"],
        }
    except Exception as e:
        logger.error(f"Failed to post Fathom webhook to Slack: {e}")
        return {"success": False, "error": str(e)}


@app.post("/webhook/fathom")
async def fathom_webhook(payload: FathomWebhookPayload, background_tasks: BackgroundTasks):
    """Receive webhook from Fathom when a new recording is ready.

    Posts meeting info to Slack. Returns 200 immediately to acknowledge receipt,
    then processes in background.
    """
    logger.info(f"Received Fathom webhook for recording {payload.recording_id}: {payload.title}")

    # Process in background so we return 200 quickly
    background_tasks.add_task(_post_fathom_webhook_to_slack, payload)

    return {"received": True, "recording_id": payload.recording_id}


HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Document Quality Analyzer</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f6f7fb; color: #222; }
    header { background: #111827; color: #fff; padding: 16px 24px; }
    main { max-width: 960px; margin: 24px auto; background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    label { display: block; margin-top: 16px; font-weight: 600; }
    input, select { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; margin-top: 6px; }
    button { margin-top: 20px; padding: 12px 16px; background: #2563eb; color: #fff; border: none; border-radius: 10px; cursor: pointer; font-weight: 700; }
    button:disabled { background: #93c5fd; cursor: not-allowed; }
    .row { display: flex; gap: 12px; margin-top: 12px; }
    .row .field { flex: 1; }
    .chips { display: flex; gap: 12px; margin-top: 12px; }
    .chip { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
    .chip input { width: auto; margin: 0; }
    pre { background: #0b1021; color: #e5e7eb; padding: 16px; border-radius: 10px; overflow: auto; }
    .muted { color: #6b7280; font-size: 14px; }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #eef2ff; color: #4338ca; font-weight: 700; font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <h2>Document Quality Analyzer</h2>
    <p class="muted">Paste a Google Doc/Slides URL, get a score, and post to Slack.</p>
  </header>
  <main>
    <form id="analyze-form">
      <label for="url">Document URL</label>
      <input id="url" name="url" placeholder="https://docs.google.com/document/d/..." required />

      <div class="row">
        <div class="field">
          <label for="provider">Provider</label>
          <select id="provider" name="provider">
            <option value="openai">OpenAI (default)</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
          </select>
        </div>
        <div class="field">
          <label for="type">Type</label>
          <select id="type" name="type">
            <option value="">Auto-detect</option>
            <option value="proposal">Proposal</option>
            <option value="kickoff">Kickoff</option>
          </select>
        </div>
      </div>

      <div class="chips">
        <label class="chip"><input type="checkbox" id="slack" /> Post to Slack</label>
        <label class="chip"><input type="checkbox" id="comment" /> Add Doc comment</label>
      </div>

      <button type="submit">Run Analysis</button>
      <div id="status" class="muted"></div>
    </form>

    <hr style="margin: 28px 0; border: none; border-top: 1px solid #e5e7eb;">

    <form id="fathom-form">
      <h3 style="margin: 0 0 8px 0;">Fathom Transcript</h3>
      <p class="muted" style="margin-top: 0;">Analyze a Fathom recording by its recording ID.</p>

      <label for="recording_id">Recording ID</label>
      <input id="recording_id" name="recording_id" placeholder="recording id..." required />

      <div class="row">
        <div class="field">
          <label for="fathom_provider">Provider</label>
          <select id="fathom_provider" name="provider">
            <option value="openai">OpenAI (default)</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
          </select>
        </div>
        <div class="field">
          <label for="call_type">Call Type</label>
          <select id="call_type" name="call_type">
            <option value="sales">Sales (BANNT)</option>
            <option value="client">Client (opportunities/concerns)</option>
          </select>
        </div>
      </div>

      <div class="chips">
        <label class="chip"><input type="checkbox" id="fathom_slack" /> Post to Slack</label>
      </div>

      <button type="submit">Analyze Transcript</button>
      <div id="fathom_status" class="muted"></div>
    </form>

    <section style="margin-top: 24px;">
      <div id="result"></div>
    </section>
  </main>

  <script>
    const form = document.getElementById('analyze-form');
    const status = document.getElementById('status');
    const result = document.getElementById('result');
    const fathomForm = document.getElementById('fathom-form');
    const fathomStatus = document.getElementById('fathom_status');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      result.innerHTML = '';
      status.textContent = 'Running analysis...';
      const btn = form.querySelector('button');
      btn.disabled = true;

      const payload = {
        url: document.getElementById('url').value.trim(),
        provider: document.getElementById('provider').value,
        slack: document.getElementById('slack').checked,
        comment: document.getElementById('comment').checked,
      };
      const docType = document.getElementById('type').value;
      if (docType) payload.type = docType;

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Request failed');

        const score = data.analysis.score ? data.analysis.score.overall : '—';
        const issueCount = data.analysis.issues.length;
        const slack = data.slack?.url ? `<a href="${data.slack.url}" target="_blank">View Slack message</a>` : (payload.slack ? 'Posted to Slack' : 'Slack not requested');
        const comment = data.comment?.success ? 'Comment added' : (payload.comment ? 'Comment attempted (check logs)' : 'No comment');

        result.innerHTML = `
          <h3>${data.analysis.document_title} <span class="pill">${data.analysis.document_type}</span></h3>
          <p class="muted">Provider: ${data.analysis.llm_provider} • Score: ${score}/100 • Issues: ${issueCount}</p>
          <p class="muted">${slack} • ${comment}</p>
          <pre>${JSON.stringify(data.analysis, null, 2)}</pre>
        `;
        status.textContent = '';
      } catch (err) {
        console.error(err);
        status.textContent = err.message;
      } finally {
        btn.disabled = false;
      }
    });

    fathomForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      result.innerHTML = '';
      fathomStatus.textContent = 'Fetching transcript + running analysis...';
      const btn = fathomForm.querySelector('button');
      btn.disabled = true;

      const payload = {
        recording_id: document.getElementById('recording_id').value.trim(),
        provider: document.getElementById('fathom_provider').value,
        is_sales_call: document.getElementById('call_type').value === 'sales',
        slack: document.getElementById('fathom_slack').checked,
      };

      try {
        const res = await fetch('/api/analyze-fathom', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Request failed');

        const score = data.analysis.score ? data.analysis.score.overall : '—';
        const issueCount = data.analysis.issues.length;
        const slack = data.slack?.url ? `<a href="${data.slack.url}" target="_blank">View Slack message</a>` : (payload.slack ? 'Posted to Slack' : 'Slack not requested');

        result.innerHTML = `
          <h3>${data.analysis.document_title} <span class="pill">${data.analysis.document_type}</span></h3>
          <p class="muted">Provider: ${data.analysis.llm_provider} • Score: ${score}/100 • Issues: ${issueCount}</p>
          <p class="muted">${slack}</p>
          <pre>${JSON.stringify({ analysis: data.analysis, fathom: data.fathom }, null, 2)}</pre>
        `;
        fathomStatus.textContent = '';
      } catch (err) {
        console.error(err);
        fathomStatus.textContent = err.message;
      } finally {
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve a minimal UI for manual testing."""
    return HTMLResponse(content=HTML_PAGE)

