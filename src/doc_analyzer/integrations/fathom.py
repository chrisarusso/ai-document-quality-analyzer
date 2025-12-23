"""Fathom API client for accessing meeting transcripts."""

import httpx
from datetime import datetime
from typing import Optional

from ..config import get_settings
from ..models import FathomMeeting, FathomTranscript


class FathomClient:
    """Client for Fathom API."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.fathom_api_key
        self.base_url = settings.fathom_api_base
        self.headers = {"X-Api-Key": self.api_key}

    async def list_meetings(self, limit: int = 10) -> list[FathomMeeting]:
        """List recent meetings."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/meetings",
                headers=self.headers,
                params={"limit": limit},
            )
            response.raise_for_status()
            data = response.json()

            meetings = []
            for item in data.get("recordings", []):
                meetings.append(FathomMeeting(
                    id=item["id"],
                    title=item.get("title", "Untitled"),
                    url=item.get("url", ""),
                    created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                    scheduled_start_time=self._parse_datetime(item.get("scheduled_start_time")),
                    scheduled_end_time=self._parse_datetime(item.get("scheduled_end_time")),
                    calendar_invitees_domains_type=item.get("calendar_invitees_domains_type"),
                ))
            return meetings

    async def get_transcript(self, recording_id: str) -> FathomTranscript:
        """Get transcript for a specific recording."""
        async with httpx.AsyncClient() as client:
            # Get meeting details
            meeting_response = await client.get(
                f"{self.base_url}/recordings/{recording_id}",
                headers=self.headers,
            )
            meeting_response.raise_for_status()
            meeting_data = meeting_response.json()

            # Get transcript
            transcript_response = await client.get(
                f"{self.base_url}/recordings/{recording_id}/transcript",
                headers=self.headers,
            )
            transcript_response.raise_for_status()
            transcript_data = transcript_response.json()

            # Get summary
            summary_response = await client.get(
                f"{self.base_url}/recordings/{recording_id}/summary",
                headers=self.headers,
            )
            summary_data = summary_response.json() if summary_response.status_code == 200 else {}

            return FathomTranscript(
                recording_id=recording_id,
                title=meeting_data.get("title", "Untitled"),
                url=meeting_data.get("url", ""),
                share_url=meeting_data.get("share_url"),
                created_at=datetime.fromisoformat(meeting_data["created_at"].replace("Z", "+00:00")),
                transcript=transcript_data.get("transcript", []),
                summary=summary_data.get("default_summary", {}).get("markdown_formatted"),
                action_items=summary_data.get("action_items", []),
            )

    async def test_connection(self) -> dict:
        """Test API connection and return account info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/meetings",
                headers=self.headers,
                params={"limit": 1},
            )
            if response.status_code == 401:
                return {"success": False, "error": "Invalid API key"}
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "meetings_available": len(data.get("recordings", [])) > 0,
                    "rate_limit_remaining": response.headers.get("RateLimit-Remaining"),
                }
            return {"success": False, "error": f"HTTP {response.status_code}"}

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
