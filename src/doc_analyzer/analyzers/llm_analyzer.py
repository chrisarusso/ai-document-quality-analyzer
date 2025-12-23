"""LLM-based document analysis with multiple provider support."""

import json
from typing import Optional, Literal
from abc import ABC, abstractmethod

from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai

from ..config import get_settings
from ..models import Issue, IssueCategory, IssueSeverity


LLMProvider = Literal["openai", "anthropic", "google"]


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def analyze(self, text: str, prompt: str) -> str:
        """Send text to LLM and get response."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        settings = get_settings()
        self.client = OpenAI(api_key=api_key or settings.openai_api_key)
        self.model = model

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    def analyze(self, text: str, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-haiku-20241022"):
        settings = get_settings()
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model

    @property
    def name(self) -> str:
        return f"anthropic/{self.model}"

    def analyze(self, text: str, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": f"{prompt}\n\n---\n\nDocument to analyze:\n\n{text}"},
            ],
        )
        return response.content[0].text


class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        settings = get_settings()
        genai.configure(api_key=api_key or settings.google_api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model

    @property
    def name(self) -> str:
        return f"google/{self.model_name}"

    def analyze(self, text: str, prompt: str) -> str:
        response = self.model.generate_content(
            f"{prompt}\n\n---\n\nDocument to analyze:\n\n{text}",
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        return response.text


class LLMAnalyzer:
    """Multi-provider LLM analyzer for document quality."""

    # Prompt for spelling/grammar analysis
    SPELLING_GRAMMAR_PROMPT = """You are a professional document editor. Analyze the following document for spelling, grammar, and spacing issues.

Return a JSON object with this structure:
{
  "issues": [
    {
      "category": "spelling|grammar|spacing",
      "text": "the problematic text",
      "suggestion": "the corrected text",
      "location": "slide/line number or context hint",
      "severity": "high|medium|low"
    }
  ],
  "summary": {
    "spelling_errors": 0,
    "grammar_errors": 0,
    "spacing_errors": 0
  }
}

Be strict but accurate. Only flag clear errors, not stylistic preferences.
For technical terms, brand names, and proper nouns, do NOT flag as spelling errors.
For spacing: flag double spaces, missing spaces after punctuation, inconsistent spacing."""

    # Prompt for content/completeness analysis
    CONTENT_PROMPT = """You are a business document reviewer. Analyze this document for content quality and completeness.

Return a JSON object with this structure:
{
  "issues": [
    {
      "category": "missing_content|style|formatting",
      "title": "brief issue title",
      "description": "what's missing or problematic",
      "suggestion": "how to fix it",
      "location": "where in the document",
      "severity": "critical|high|medium|low",
      "affects_score": true
    }
  ],
  "required_sections_found": ["list", "of", "sections"],
  "required_sections_missing": ["list", "of", "missing"],
  "style_observations": ["passive voice instances", "jargon found", "etc"]
}

For proposals, look for: executive summary, scope, timeline, budget, team, next steps.
For kickoffs, look for: introductions, project overview, goals, risks, schedule, next steps.
Flag passive voice and jargon as low severity (informational only)."""

    # Prompt for BANNT analysis (sales calls)
    BANNT_PROMPT = """You are a sales call analyst. Analyze this call transcript using the BANNT framework.

Return a JSON object with this structure:
{
  "budget": {
    "discussed": true/false,
    "notes": "summary of budget discussion",
    "range": "$X - $Y if mentioned"
  },
  "authority": {
    "identified": true/false,
    "notes": "who has decision-making authority",
    "decision_maker": "name if identified"
  },
  "need": {
    "articulated": true/false,
    "notes": "summary of pain points and needs",
    "pain_points": ["list", "of", "pain points"]
  },
  "next_steps": {
    "scheduled": true/false,
    "notes": "what follow-up was agreed",
    "action_items": ["list", "of", "actions"]
  },
  "timeline": {
    "discussed": true/false,
    "notes": "timeline information",
    "target_date": "date if mentioned"
  },
  "overall_score": 0-5,
  "recommendations": ["suggestions for follow-up"]
}"""

    # Prompt for client call analysis
    CLIENT_CALL_PROMPT = """You are a client relationship analyst. Analyze this call transcript for opportunities and concerns.

Return a JSON object with this structure:
{
  "opportunities": [
    {
      "type": "expansion|referral|additional_work",
      "description": "what was mentioned",
      "quote": "relevant quote from transcript",
      "timestamp": "if available"
    }
  ],
  "concerns": [
    {
      "type": "functionality|satisfaction|schedule|budget",
      "severity": "critical|high|medium|low",
      "description": "what the concern is",
      "quote": "relevant quote",
      "timestamp": "if available",
      "recommended_action": "what to do about it"
    }
  ],
  "overall_sentiment": "positive|neutral|negative|mixed",
  "action_items_mentioned": ["list of action items"],
  "follow_up_needed": true/false,
  "summary": "brief summary of call"
}"""

    def __init__(self, provider: LLMProvider = "openai"):
        self.provider = self._create_provider(provider)

    def _create_provider(self, provider: LLMProvider) -> BaseLLMProvider:
        """Create the appropriate LLM provider."""
        if provider == "openai":
            return OpenAIProvider()
        elif provider == "anthropic":
            return AnthropicProvider()
        elif provider == "google":
            return GoogleProvider()
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def analyze_spelling_grammar(self, text: str) -> dict:
        """Analyze document for spelling and grammar issues."""
        response = self.provider.analyze(text, self.SPELLING_GRAMMAR_PROMPT)
        return self._parse_json(response)

    def analyze_content(self, text: str) -> dict:
        """Analyze document for content quality and completeness."""
        response = self.provider.analyze(text, self.CONTENT_PROMPT)
        return self._parse_json(response)

    def analyze_bannt(self, transcript: str) -> dict:
        """Analyze sales call transcript using BANNT framework."""
        response = self.provider.analyze(transcript, self.BANNT_PROMPT)
        return self._parse_json(response)

    def analyze_client_call(self, transcript: str) -> dict:
        """Analyze client call for opportunities and concerns."""
        response = self.provider.analyze(transcript, self.CLIENT_CALL_PROMPT)
        return self._parse_json(response)

    def _parse_json(self, response: str) -> dict:
        """Parse JSON from LLM response."""
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse response: {e}", "raw": response}

    @property
    def provider_name(self) -> str:
        """Get current provider name."""
        return self.provider.name
