"""Google Slides text extraction."""

import os
import re
from typing import Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Scopes needed for reading slides and adding comments
SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSlidesExtractor:
    """Extract text content from Google Slides presentations."""

    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.slides_service = None
        self.drive_service = None

    def authenticate(self) -> bool:
        """Authenticate with Google APIs."""
        # Check for existing token
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Refresh or get new token
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Download from Google Cloud Console → APIs & Services → Credentials"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save token for next run
            with open(self.token_path, "w") as token:
                token.write(self.creds.to_json())

        # Build services
        self.slides_service = build("slides", "v1", credentials=self.creds)
        self.drive_service = build("drive", "v3", credentials=self.creds)
        return True

    def extract_text(self, url: str) -> dict:
        """Extract all text from a Google Slides presentation.

        Args:
            url: Google Slides URL

        Returns:
            dict with title, slides (list of slide texts), and full_text
        """
        if not self.slides_service:
            self.authenticate()

        presentation_id = self._extract_id(url)

        try:
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            title = presentation.get("title", "Untitled")
            slides_text = []

            for i, slide in enumerate(presentation.get("slides", []), 1):
                slide_content = self._extract_slide_text(slide)
                slides_text.append({
                    "slide_number": i,
                    "slide_id": slide.get("objectId"),
                    "text": slide_content,
                })

            full_text = "\n\n".join([
                f"--- Slide {s['slide_number']} ---\n{s['text']}"
                for s in slides_text
            ])

            return {
                "presentation_id": presentation_id,
                "title": title,
                "slides": slides_text,
                "full_text": full_text,
                "slide_count": len(slides_text),
            }

        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Presentation not found: {presentation_id}")
            if e.resp.status == 403:
                raise PermissionError(f"Access denied to presentation: {presentation_id}")
            raise

    def add_comment(self, url: str, content: str) -> dict:
        """Add a comment to the presentation via Drive API.

        Note: This adds an unanchored comment (not tied to specific text).
        """
        if not self.drive_service:
            self.authenticate()

        file_id = self._extract_id(url)

        try:
            comment = self.drive_service.comments().create(
                fileId=file_id,
                fields="id,content,createdTime",
                body={"content": content}
            ).execute()

            return {
                "success": True,
                "comment_id": comment.get("id"),
                "created_at": comment.get("createdTime"),
            }

        except HttpError as e:
            return {"success": False, "error": str(e)}

    def _extract_id(self, url: str) -> str:
        """Extract presentation ID from URL."""
        # Handle various URL formats
        patterns = [
            r"/presentation/d/([a-zA-Z0-9_-]+)",
            r"/d/([a-zA-Z0-9_-]+)",
            r"^([a-zA-Z0-9_-]+)$",  # Just the ID
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract presentation ID from: {url}")

    def _extract_slide_text(self, slide: dict) -> str:
        """Extract all text from a single slide."""
        texts = []

        for element in slide.get("pageElements", []):
            # Text boxes and shapes
            if "shape" in element:
                shape = element["shape"]
                if "text" in shape:
                    texts.append(self._extract_text_content(shape["text"]))

            # Tables
            if "table" in element:
                table = element["table"]
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        if "text" in cell:
                            texts.append(self._extract_text_content(cell["text"]))

        return "\n".join(filter(None, texts))

    def _extract_text_content(self, text_obj: dict) -> str:
        """Extract plain text from a text object."""
        content = []
        for element in text_obj.get("textElements", []):
            if "textRun" in element:
                content.append(element["textRun"].get("content", ""))
        return "".join(content).strip()
