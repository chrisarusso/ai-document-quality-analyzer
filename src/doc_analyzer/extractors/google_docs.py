"""Google Docs text extraction."""

import os
import re
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Unified scopes for Docs, Slides, and Drive (comments)
SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/drive",
]


class GoogleDocsExtractor:
    """Extract text content from Google Docs."""

    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.docs_service = None
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
        self.docs_service = build("docs", "v1", credentials=self.creds)
        self.drive_service = build("drive", "v3", credentials=self.creds)
        return True

    def extract_text(self, url: str) -> dict:
        """Extract all text from a Google Doc.

        Args:
            url: Google Docs URL

        Returns:
            dict with title, content sections, and full_text
        """
        if not self.docs_service:
            self.authenticate()

        document_id = self._extract_id(url)

        try:
            document = self.docs_service.documents().get(
                documentId=document_id
            ).execute()

            title = document.get("title", "Untitled")
            content = document.get("body", {}).get("content", [])

            sections = []
            full_text = []

            for element in content:
                if "paragraph" in element:
                    para = element["paragraph"]
                    text = self._extract_paragraph_text(para)
                    if text:
                        full_text.append(text)

                        # Check if this is a heading
                        style = para.get("paragraphStyle", {})
                        named_style = style.get("namedStyleType", "NORMAL_TEXT")

                        if named_style.startswith("HEADING"):
                            sections.append({
                                "type": named_style,
                                "text": text,
                            })

                elif "table" in element:
                    table_text = self._extract_table_text(element["table"])
                    if table_text:
                        full_text.append(table_text)

            return {
                "document_id": document_id,
                "title": title,
                "sections": sections,
                "full_text": "\n".join(full_text),
                "word_count": len("\n".join(full_text).split()),
            }

        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Document not found: {document_id}")
            if e.resp.status == 403:
                raise PermissionError(f"Access denied to document: {document_id}")
            raise

    def add_comment(self, url: str, content: str) -> dict:
        """Add a comment to the document via Drive API.

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
        """Extract document ID from URL."""
        patterns = [
            r"/document/d/([a-zA-Z0-9_-]+)",
            r"/d/([a-zA-Z0-9_-]+)",
            r"^([a-zA-Z0-9_-]+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract document ID from: {url}")

    def _extract_paragraph_text(self, paragraph: dict) -> str:
        """Extract text from a paragraph element."""
        texts = []
        for element in paragraph.get("elements", []):
            if "textRun" in element:
                texts.append(element["textRun"].get("content", ""))
        return "".join(texts).strip()

    def _extract_table_text(self, table: dict) -> str:
        """Extract text from a table element."""
        rows = []
        for row in table.get("tableRows", []):
            cells = []
            for cell in row.get("tableCells", []):
                cell_text = []
                for content in cell.get("content", []):
                    if "paragraph" in content:
                        cell_text.append(self._extract_paragraph_text(content["paragraph"]))
                cells.append(" ".join(cell_text))
            rows.append(" | ".join(cells))
        return "\n".join(rows)
