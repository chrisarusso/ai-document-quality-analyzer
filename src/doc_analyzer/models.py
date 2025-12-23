"""Data models for Document Quality Analyzer."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """Types of documents that can be analyzed."""
    PROPOSAL = "proposal"
    KICKOFF = "kickoff"
    TRANSCRIPT_SALES = "transcript_sales"
    TRANSCRIPT_CLIENT = "transcript_client"


class IssueSeverity(str, Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"  # Affects score heavily
    HIGH = "high"          # Affects score
    MEDIUM = "medium"      # Affects score slightly
    LOW = "low"            # Flagged only, no score impact
    INFO = "info"          # Informational, no score impact


class IssueCategory(str, Enum):
    """Categories of issues."""
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    SPACING = "spacing"
    FORMATTING = "formatting"
    MATH = "math"
    MISSING_CONTENT = "missing_content"
    STYLE = "style"
    BANNT = "bannt"
    OPPORTUNITY = "opportunity"
    CONCERN = "concern"


class Issue(BaseModel):
    """A detected issue in a document."""
    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    location: Optional[str] = None  # Line number, slide number, timestamp
    context: Optional[str] = None   # Surrounding text
    suggestion: Optional[str] = None  # Recommended fix
    affects_score: bool = True


class ScoreBreakdown(BaseModel):
    """Breakdown of scores by category."""
    spelling_grammar: int = Field(ge=0, le=100, default=100)
    required_content: int = Field(ge=0, le=100, default=100)
    math_accuracy: int = Field(ge=0, le=100, default=100)

    @property
    def overall(self) -> int:
        """Calculate weighted overall score."""
        # Spelling/grammar: 50%, Required content: 40%, Math: 10%
        return int(
            self.spelling_grammar * 0.5 +
            self.required_content * 0.4 +
            self.math_accuracy * 0.1
        )


class BANNTScore(BaseModel):
    """BANNT scoring for sales calls."""
    budget: bool = False
    budget_notes: str = ""
    authority: bool = False
    authority_notes: str = ""
    need: bool = False
    need_notes: str = ""
    next_steps: bool = False
    next_steps_notes: str = ""
    timeline: bool = False
    timeline_notes: str = ""

    @property
    def score(self) -> int:
        """Calculate BANNT score (0-5)."""
        return sum([
            self.budget,
            self.authority,
            self.need,
            self.next_steps,
            self.timeline,
        ])


class AnalysisResult(BaseModel):
    """Result of analyzing a document."""
    document_url: str
    document_title: str
    document_type: DocumentType
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    llm_provider: str

    # Scoring
    score: Optional[ScoreBreakdown] = None
    bannt_score: Optional[BANNTScore] = None

    # Issues
    issues: list[Issue] = Field(default_factory=list)

    # Raw content (for debugging)
    text_length: int = 0

    @property
    def issues_by_severity(self) -> dict[str, list[Issue]]:
        """Group issues by severity."""
        result = {s.value: [] for s in IssueSeverity}
        for issue in self.issues:
            result[issue.severity.value].append(issue)
        return result

    @property
    def scored_issues(self) -> list[Issue]:
        """Issues that affect the score."""
        return [i for i in self.issues if i.affects_score]

    @property
    def flagged_issues(self) -> list[Issue]:
        """Issues that are flagged but don't affect score."""
        return [i for i in self.issues if not i.affects_score]


class FathomTranscript(BaseModel):
    """Fathom meeting transcript data."""
    recording_id: str
    title: str
    url: str
    share_url: Optional[str] = None
    created_at: datetime
    transcript: list[dict]  # [{speaker: {display_name, email}, text, timestamp}]
    summary: Optional[str] = None
    action_items: list[dict] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Get full transcript as text."""
        lines = []
        for entry in self.transcript:
            speaker = entry.get("speaker", {}).get("display_name", "Unknown")
            text = entry.get("text", "")
            timestamp = entry.get("timestamp", "")
            lines.append(f"[{timestamp}] {speaker}: {text}")
        return "\n".join(lines)


class FathomMeeting(BaseModel):
    """Fathom meeting metadata."""
    id: str
    title: str
    url: str
    created_at: datetime
    scheduled_start_time: Optional[datetime] = None
    scheduled_end_time: Optional[datetime] = None
    calendar_invitees_domains_type: Optional[str] = None
