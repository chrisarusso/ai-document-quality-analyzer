"""Main quality analyzer that coordinates extraction, analysis, and scoring."""

from datetime import datetime
from typing import Optional

from .llm_analyzer import LLMAnalyzer, LLMProvider
from ..extractors.google_slides import GoogleSlidesExtractor
from ..extractors.google_docs import GoogleDocsExtractor
from ..models import (
    AnalysisResult, DocumentType, Issue, IssueCategory,
    IssueSeverity, ScoreBreakdown, BANNTScore
)


class QualityAnalyzer:
    """Main document quality analyzer."""

    def __init__(self, provider: LLMProvider = "openai"):
        self.llm = LLMAnalyzer(provider=provider)
        self.slides_extractor = GoogleSlidesExtractor()
        self.docs_extractor = GoogleDocsExtractor()

    def analyze_url(
        self,
        url: str,
        doc_type: Optional[DocumentType] = None
    ) -> AnalysisResult:
        """Analyze a Google Doc or Slides URL.

        Args:
            url: Google Docs/Slides URL
            doc_type: Document type (auto-detected if not provided)

        Returns:
            AnalysisResult with score and issues
        """
        # Detect document type from URL
        if "/presentation/" in url:
            extractor = self.slides_extractor
            doc_type = doc_type or self._infer_slides_type(url)
        elif "/document/" in url:
            extractor = self.docs_extractor
            doc_type = doc_type or DocumentType.PROPOSAL
        else:
            raise ValueError(f"Unsupported URL format: {url}")

        # Extract text
        extractor.authenticate()
        extracted = extractor.extract_text(url)
        text = extracted.get("full_text", "")
        title = extracted.get("title", "Untitled")

        # Analyze with LLM
        issues = []

        # Spelling/grammar analysis
        sg_result = self.llm.analyze_spelling_grammar(text[:30000])  # Limit for token cost
        issues.extend(self._convert_sg_issues(sg_result))

        # Content analysis
        content_result = self.llm.analyze_content(text[:30000])
        issues.extend(self._convert_content_issues(content_result))

        # Calculate score
        score = self._calculate_score(issues, sg_result, content_result)

        return AnalysisResult(
            document_url=url,
            document_title=title,
            document_type=doc_type,
            analyzed_at=datetime.utcnow(),
            llm_provider=self.llm.provider_name,
            score=score,
            issues=issues,
            text_length=len(text),
        )

    def analyze_transcript(
        self,
        transcript: str,
        is_sales_call: bool = True,
        title: str = "Call Transcript"
    ) -> AnalysisResult:
        """Analyze a call transcript.

        Args:
            transcript: Full transcript text
            is_sales_call: True for sales (BANNT), False for client call
            title: Transcript title

        Returns:
            AnalysisResult with BANNT score or opportunity/concern analysis
        """
        doc_type = DocumentType.TRANSCRIPT_SALES if is_sales_call else DocumentType.TRANSCRIPT_CLIENT
        issues = []
        bannt_score = None

        if is_sales_call:
            # BANNT analysis
            result = self.llm.analyze_bannt(transcript[:30000])
            bannt_score = self._convert_bannt(result)
            issues.extend(self._bannt_to_issues(result))
        else:
            # Client call analysis
            result = self.llm.analyze_client_call(transcript[:30000])
            issues.extend(self._convert_client_call_issues(result))

        return AnalysisResult(
            document_url="transcript",
            document_title=title,
            document_type=doc_type,
            analyzed_at=datetime.utcnow(),
            llm_provider=self.llm.provider_name,
            bannt_score=bannt_score,
            issues=issues,
            text_length=len(transcript),
        )

    def _infer_slides_type(self, url: str) -> DocumentType:
        """Infer document type from slides URL or content."""
        # Simple heuristic based on common patterns
        url_lower = url.lower()
        if "kickoff" in url_lower or "kick-off" in url_lower:
            return DocumentType.KICKOFF
        return DocumentType.PROPOSAL

    def _convert_sg_issues(self, result: dict) -> list[Issue]:
        """Convert spelling/grammar results to Issue objects."""
        issues = []
        for item in result.get("issues", []):
            category = {
                "spelling": IssueCategory.SPELLING,
                "grammar": IssueCategory.GRAMMAR,
                "spacing": IssueCategory.SPACING,
            }.get(item.get("category", ""), IssueCategory.SPELLING)

            severity = {
                "high": IssueSeverity.HIGH,
                "medium": IssueSeverity.MEDIUM,
                "low": IssueSeverity.LOW,
            }.get(item.get("severity", "medium"), IssueSeverity.MEDIUM)

            issues.append(Issue(
                category=category,
                severity=severity,
                title=f"{category.value.title()} error: {item.get('text', '')[:30]}",
                description=f"Found: '{item.get('text', '')}'",
                location=item.get("location"),
                suggestion=item.get("suggestion"),
                affects_score=True,
            ))
        return issues

    def _convert_content_issues(self, result: dict) -> list[Issue]:
        """Convert content analysis results to Issue objects."""
        issues = []

        # Missing sections
        for section in result.get("required_sections_missing", []):
            issues.append(Issue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.HIGH,
                title=f"Missing section: {section}",
                description=f"Required section '{section}' was not found in the document",
                suggestion=f"Add a section for {section}",
                affects_score=True,
            ))

        # Other issues from LLM
        for item in result.get("issues", []):
            category = {
                "missing_content": IssueCategory.MISSING_CONTENT,
                "style": IssueCategory.STYLE,
                "formatting": IssueCategory.FORMATTING,
            }.get(item.get("category", ""), IssueCategory.STYLE)

            severity = {
                "critical": IssueSeverity.CRITICAL,
                "high": IssueSeverity.HIGH,
                "medium": IssueSeverity.MEDIUM,
                "low": IssueSeverity.LOW,
            }.get(item.get("severity", "medium"), IssueSeverity.MEDIUM)

            affects_score = item.get("affects_score", severity != IssueSeverity.LOW)

            issues.append(Issue(
                category=category,
                severity=severity,
                title=item.get("title", "Content issue"),
                description=item.get("description", ""),
                location=item.get("location"),
                suggestion=item.get("suggestion"),
                affects_score=affects_score,
            ))

        # Style observations (flagged only, not scored)
        for obs in result.get("style_observations", []):
            issues.append(Issue(
                category=IssueCategory.STYLE,
                severity=IssueSeverity.INFO,
                title="Style observation",
                description=obs,
                affects_score=False,
            ))

        return issues

    def _convert_bannt(self, result: dict) -> BANNTScore:
        """Convert BANNT analysis to BANNTScore."""
        return BANNTScore(
            budget=result.get("budget", {}).get("discussed", False),
            budget_notes=result.get("budget", {}).get("notes", ""),
            authority=result.get("authority", {}).get("identified", False),
            authority_notes=result.get("authority", {}).get("notes", ""),
            need=result.get("need", {}).get("articulated", False),
            need_notes=result.get("need", {}).get("notes", ""),
            next_steps=result.get("next_steps", {}).get("scheduled", False),
            next_steps_notes=result.get("next_steps", {}).get("notes", ""),
            timeline=result.get("timeline", {}).get("discussed", False),
            timeline_notes=result.get("timeline", {}).get("notes", ""),
        )

    def _bannt_to_issues(self, result: dict) -> list[Issue]:
        """Convert BANNT gaps to issues."""
        issues = []
        elements = [
            ("budget", "Budget not discussed"),
            ("authority", "Decision maker not identified"),
            ("need", "Pain points not articulated"),
            ("next_steps", "No follow-up scheduled"),
            ("timeline", "Timeline not discussed"),
        ]

        for key, title in elements:
            data = result.get(key, {})
            is_ok = data.get("discussed", False) or data.get("identified", False) or \
                    data.get("articulated", False) or data.get("scheduled", False)
            if not is_ok:
                issues.append(Issue(
                    category=IssueCategory.BANNT,
                    severity=IssueSeverity.MEDIUM,
                    title=title,
                    description=data.get("notes", "Not covered in call"),
                    affects_score=False,  # BANNT has its own score
                ))

        # Add recommendations as info
        for rec in result.get("recommendations", []):
            issues.append(Issue(
                category=IssueCategory.BANNT,
                severity=IssueSeverity.INFO,
                title="Recommendation",
                description=rec,
                affects_score=False,
            ))

        return issues

    def _convert_client_call_issues(self, result: dict) -> list[Issue]:
        """Convert client call analysis to issues."""
        issues = []

        # Opportunities
        for opp in result.get("opportunities", []):
            issues.append(Issue(
                category=IssueCategory.OPPORTUNITY,
                severity=IssueSeverity.INFO,
                title=f"Opportunity: {opp.get('type', 'unknown')}",
                description=opp.get("description", ""),
                context=opp.get("quote"),
                location=opp.get("timestamp"),
                affects_score=False,
            ))

        # Concerns
        for concern in result.get("concerns", []):
            severity = {
                "critical": IssueSeverity.CRITICAL,
                "high": IssueSeverity.HIGH,
                "medium": IssueSeverity.MEDIUM,
                "low": IssueSeverity.LOW,
            }.get(concern.get("severity", "medium"), IssueSeverity.MEDIUM)

            issues.append(Issue(
                category=IssueCategory.CONCERN,
                severity=severity,
                title=f"Concern: {concern.get('type', 'unknown')}",
                description=concern.get("description", ""),
                context=concern.get("quote"),
                location=concern.get("timestamp"),
                suggestion=concern.get("recommended_action"),
                affects_score=False,
            ))

        return issues

    def _calculate_score(
        self,
        issues: list[Issue],
        sg_result: dict,
        content_result: dict
    ) -> ScoreBreakdown:
        """Calculate document score based on issues."""
        # Count issues by category
        spelling_grammar_issues = sum(
            1 for i in issues
            if i.category in [IssueCategory.SPELLING, IssueCategory.GRAMMAR, IssueCategory.SPACING]
            and i.affects_score
        )
        missing_content_issues = sum(
            1 for i in issues
            if i.category == IssueCategory.MISSING_CONTENT
            and i.affects_score
        )

        # Scoring logic (deduct points per issue, min 0)
        # Spelling/grammar: start at 100, lose 5 per issue
        sg_score = max(0, 100 - (spelling_grammar_issues * 5))

        # Required content: start at 100, lose 15 per missing section
        content_score = max(0, 100 - (missing_content_issues * 15))

        # Math: not yet implemented, default to 100
        math_score = 100

        return ScoreBreakdown(
            spelling_grammar=sg_score,
            required_content=content_score,
            math_accuracy=math_score,
        )
