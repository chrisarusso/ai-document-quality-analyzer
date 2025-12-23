"""Slack integration for posting analysis results."""

from typing import Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import get_settings
from ..models import AnalysisResult, Issue, IssueSeverity


class SlackNotifier:
    """Posts analysis results to Slack."""

    def __init__(self, token: Optional[str] = None, channel: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.slack_bot_token
        self.channel = channel or settings.slack_channel
        self.client = WebClient(token=self.token) if self.token else None

    def post_analysis(self, result: AnalysisResult, mention: str = "@chris") -> dict:
        """Post analysis result to Slack."""
        if not self.client:
            # Dry run - print to console
            message = self._format_message(result, mention)
            print(f"\n[DRY RUN] Would post to #{self.channel}:\n{message}")
            return {"success": True, "dry_run": True}

        try:
            blocks = self._build_blocks(result, mention)
            response = self.client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text=f"Document Analysis: {result.document_title}",  # Fallback
            )
            return {
                "success": True,
                "channel": response["channel"],
                "ts": response["ts"],
                "url": self._get_message_url(response),
            }
        except SlackApiError as e:
            return {"success": False, "error": str(e)}

    def test_connection(self) -> dict:
        """Test Slack connection."""
        if not self.client:
            return {"success": False, "error": "No bot token configured"}

        try:
            response = self.client.auth_test()
            return {
                "success": True,
                "team": response["team"],
                "user": response["user"],
                "bot_id": response["bot_id"],
            }
        except SlackApiError as e:
            return {"success": False, "error": str(e)}

    def _format_message(self, result: AnalysisResult, mention: str) -> str:
        """Format result as plain text message."""
        lines = [
            f"Document Analysis Complete",
            f"",
            f"Document: {result.document_title}",
            f"Type: {result.document_type.value}",
        ]

        if result.score:
            lines.append(f"Score: {result.score.overall}/100")

        if result.bannt_score:
            lines.append(f"BANNT Score: {result.bannt_score.score}/5")

        lines.append(f"Link: {result.document_url}")
        lines.append("")
        lines.append("Issues Found:")

        for issue in result.issues[:10]:  # Top 10
            severity_icon = self._severity_icon(issue.severity)
            lines.append(f"  {severity_icon} {issue.category.value}: {issue.title}")
            if issue.suggestion:
                lines.append(f"      Suggestion: {issue.suggestion}")

        if len(result.issues) > 10:
            lines.append(f"  ... and {len(result.issues) - 10} more")

        lines.append("")
        lines.append(f"cc {mention}")

        return "\n".join(lines)

    def _build_blocks(self, result: AnalysisResult, mention: str) -> list:
        """Build Slack Block Kit blocks."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Document Analysis Complete"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Document:*\n{result.document_title}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{result.document_type.value}"},
                ]
            },
        ]

        # Score section
        if result.score:
            score = result.score.overall
            score_emoji = self._score_emoji(score)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Score:* {score_emoji} {score}/100"},
            })

        if result.bannt_score:
            bannt = result.bannt_score
            bannt_text = "\n".join([
                f"{'✅' if bannt.budget else '❌'} Budget: {bannt.budget_notes or 'Not discussed'}",
                f"{'✅' if bannt.authority else '❌'} Authority: {bannt.authority_notes or 'Not identified'}",
                f"{'✅' if bannt.need else '❌'} Need: {bannt.need_notes or 'Not articulated'}",
                f"{'✅' if bannt.next_steps else '❌'} Next Steps: {bannt.next_steps_notes or 'Not scheduled'}",
                f"{'✅' if bannt.timeline else '❌'} Timeline: {bannt.timeline_notes or 'Not discussed'}",
            ])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*BANNT Score: {bannt.score}/5*\n{bannt_text}"},
            })

        # Link
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<{result.document_url}|View Document>"},
        })

        # Issues
        if result.issues:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Issues Found ({len(result.issues)}):*"},
            })

            issue_text = []
            for issue in result.issues[:10]:
                icon = self._severity_icon(issue.severity)
                line = f"{icon} *{issue.category.value}*: {issue.title}"
                if issue.location:
                    line += f" _(line {issue.location})_"
                if issue.suggestion:
                    line += f"\n     → {issue.suggestion}"
                issue_text.append(line)

            if len(result.issues) > 10:
                issue_text.append(f"_... and {len(result.issues) - 10} more_")

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(issue_text)},
            })

        # Mention
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"cc {mention}"}]
        })

        return blocks

    def _severity_icon(self, severity: IssueSeverity) -> str:
        """Get emoji for severity level."""
        return {
            IssueSeverity.CRITICAL: "🔴",
            IssueSeverity.HIGH: "🟠",
            IssueSeverity.MEDIUM: "🟡",
            IssueSeverity.LOW: "⚪",
            IssueSeverity.INFO: "ℹ️",
        }.get(severity, "⚪")

    def _score_emoji(self, score: int) -> str:
        """Get emoji for score range."""
        if score >= 90:
            return "🟢"
        if score >= 70:
            return "🟡"
        if score >= 50:
            return "🟠"
        return "🔴"

    def _get_message_url(self, response: dict) -> str:
        """Build Slack message URL."""
        # Format: https://workspace.slack.com/archives/CHANNEL_ID/pTIMESTAMP
        channel = response.get("channel", "")
        ts = response.get("ts", "").replace(".", "")
        return f"https://savaslabs.slack.com/archives/{channel}/p{ts}"
