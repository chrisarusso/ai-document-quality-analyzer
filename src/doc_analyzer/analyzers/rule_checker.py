"""Deterministic rule-based quality checks.

These run before LLM analysis and catch issues that LLMs often miss.
Each rule has a unique ID for easy filtering/disabling of false positives.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleMatch:
    """A match from a deterministic rule check."""
    rule_id: str           # Unique ID for filtering, e.g., "double-spaces"
    rule_name: str         # Human-readable name
    category: str          # spelling, grammar, spacing, formatting
    severity: str          # high, medium, low
    text: str              # The problematic text
    suggestion: str        # Suggested fix
    location: str          # Where in the document
    context: str           # Surrounding text for clarity


class RuleChecker:
    """Run deterministic quality checks on document text.

    Each rule is tagged with a unique ID so false positives can be
    easily identified and rules can be selectively disabled.
    """

    def __init__(self, disabled_rules: Optional[list[str]] = None):
        """Initialize with optional list of disabled rule IDs."""
        self.disabled_rules = set(disabled_rules or [])

    def check_all(self, text: str) -> list[RuleMatch]:
        """Run all enabled checks and return matches."""
        matches = []

        # High value checks
        if "double-spaces" not in self.disabled_rules:
            matches.extend(self._check_double_spaces(text))
        if "repeated-words" not in self.disabled_rules:
            matches.extend(self._check_repeated_words(text))
        if "missing-space-after-punct" not in self.disabled_rules:
            matches.extend(self._check_missing_space_after_punct(text))
        if "space-before-punct" not in self.disabled_rules:
            matches.extend(self._check_space_before_punct(text))
        if "unclosed-brackets" not in self.disabled_rules:
            matches.extend(self._check_unclosed_brackets(text))
        if "trailing-whitespace" not in self.disabled_rules:
            matches.extend(self._check_trailing_whitespace(text))

        # Medium value checks
        if "multiple-blank-lines" not in self.disabled_rules:
            matches.extend(self._check_multiple_blank_lines(text))
        if "inconsistent-quotes" not in self.disabled_rules:
            matches.extend(self._check_inconsistent_quotes(text))
        if "tab-characters" not in self.disabled_rules:
            matches.extend(self._check_tab_characters(text))
        if "double-hyphen-emdash" not in self.disabled_rules:
            matches.extend(self._check_double_hyphen_emdash(text))

        # Lower priority checks
        if "hidden-characters" not in self.disabled_rules:
            matches.extend(self._check_hidden_characters(text))
        if "straight-vs-curly-quotes" not in self.disabled_rules:
            matches.extend(self._check_straight_vs_curly_quotes(text))

        return matches

    def _get_line_number(self, text: str, position: int) -> int:
        """Get line number (1-indexed) for a character position."""
        return text[:position].count('\n') + 1

    def _get_context(self, text: str, start: int, end: int, context_chars: int = 30) -> str:
        """Get surrounding context for a match."""
        ctx_start = max(0, start - context_chars)
        ctx_end = min(len(text), end + context_chars)
        prefix = "..." if ctx_start > 0 else ""
        suffix = "..." if ctx_end < len(text) else ""
        return f"{prefix}{text[ctx_start:ctx_end]}{suffix}"

    # === HIGH VALUE CHECKS ===

    def _check_double_spaces(self, text: str) -> list[RuleMatch]:
        """Find double (or more) consecutive spaces."""
        matches = []
        for m in re.finditer(r' {2,}', text):
            # Skip if it's at a line boundary (indentation)
            if m.start() == 0 or text[m.start()-1] == '\n':
                continue
            matches.append(RuleMatch(
                rule_id="double-spaces",
                rule_name="Double Spaces",
                category="spacing",
                severity="medium",
                text=repr(m.group()),
                suggestion="Replace with single space",
                location=f"Line {self._get_line_number(text, m.start())}, position {m.start()}",
                context=self._get_context(text, m.start(), m.end()),
            ))
        return matches

    def _check_repeated_words(self, text: str) -> list[RuleMatch]:
        """Find repeated consecutive words like 'the the'."""
        matches = []
        # Case-insensitive match for repeated words
        for m in re.finditer(r'\b(\w+)\s+\1\b', text, re.IGNORECASE):
            # Skip common intentional repetitions
            word = m.group(1).lower()
            if word in {'that', 'had', 'very', 'really', 'blah'}:
                continue
            matches.append(RuleMatch(
                rule_id="repeated-words",
                rule_name="Repeated Word",
                category="grammar",
                severity="high",
                text=m.group(),
                suggestion=f"Remove duplicate '{m.group(1)}'",
                location=f"Line {self._get_line_number(text, m.start())}",
                context=self._get_context(text, m.start(), m.end()),
            ))
        return matches

    def _check_missing_space_after_punct(self, text: str) -> list[RuleMatch]:
        """Find missing space after punctuation like 'Hello,world'."""
        matches = []
        # Match punctuation followed immediately by a letter (not in URLs, numbers, etc.)
        for m in re.finditer(r'([.,;:!?])([A-Za-z])', text):
            # Skip if it looks like a URL, file extension, or abbreviation
            before = text[max(0, m.start()-10):m.start()]
            if any(x in before.lower() for x in ['http', 'www.', 'ftp', '.com', '.org']):
                continue
            # Skip decimal numbers like "3.5"
            if m.group(1) == '.' and m.start() > 0 and text[m.start()-1].isdigit():
                continue
            matches.append(RuleMatch(
                rule_id="missing-space-after-punct",
                rule_name="Missing Space After Punctuation",
                category="spacing",
                severity="medium",
                text=m.group(),
                suggestion=f"{m.group(1)} {m.group(2)}",
                location=f"Line {self._get_line_number(text, m.start())}",
                context=self._get_context(text, m.start(), m.end()),
            ))
        return matches

    def _check_space_before_punct(self, text: str) -> list[RuleMatch]:
        """Find space before punctuation like 'Hello ,'."""
        matches = []
        for m in re.finditer(r'(\w)\s+([.,;:!?])', text):
            matches.append(RuleMatch(
                rule_id="space-before-punct",
                rule_name="Space Before Punctuation",
                category="spacing",
                severity="medium",
                text=m.group(),
                suggestion=f"{m.group(1)}{m.group(2)}",
                location=f"Line {self._get_line_number(text, m.start())}",
                context=self._get_context(text, m.start(), m.end()),
            ))
        return matches

    def _check_unclosed_brackets(self, text: str) -> list[RuleMatch]:
        """Check for mismatched brackets and parentheses."""
        matches = []
        pairs = [('(', ')'), ('[', ']'), ('{', '}')]

        for open_char, close_char in pairs:
            open_count = text.count(open_char)
            close_count = text.count(close_char)

            if open_count != close_count:
                diff = open_count - close_count
                if diff > 0:
                    matches.append(RuleMatch(
                        rule_id="unclosed-brackets",
                        rule_name="Unclosed Bracket",
                        category="formatting",
                        severity="high",
                        text=f"{diff} unclosed '{open_char}'",
                        suggestion=f"Add {diff} closing '{close_char}'",
                        location="Document-wide",
                        context=f"Found {open_count} '{open_char}' but only {close_count} '{close_char}'",
                    ))
                else:
                    matches.append(RuleMatch(
                        rule_id="unclosed-brackets",
                        rule_name="Extra Closing Bracket",
                        category="formatting",
                        severity="high",
                        text=f"{-diff} extra '{close_char}'",
                        suggestion=f"Remove {-diff} extra '{close_char}' or add opening '{open_char}'",
                        location="Document-wide",
                        context=f"Found {close_count} '{close_char}' but only {open_count} '{open_char}'",
                    ))
        return matches

    def _check_trailing_whitespace(self, text: str) -> list[RuleMatch]:
        """Find lines ending with whitespace."""
        matches = []
        lines = text.split('\n')
        trailing_count = 0

        for i, line in enumerate(lines, 1):
            if line != line.rstrip():
                trailing_count += 1

        # Report as a single aggregate issue to avoid noise
        if trailing_count > 0:
            matches.append(RuleMatch(
                rule_id="trailing-whitespace",
                rule_name="Trailing Whitespace",
                category="formatting",
                severity="low",
                text=f"{trailing_count} line(s) with trailing whitespace",
                suggestion="Remove trailing spaces",
                location="Multiple lines",
                context=f"Found in {trailing_count} of {len(lines)} lines",
            ))
        return matches

    # === MEDIUM VALUE CHECKS ===

    def _check_multiple_blank_lines(self, text: str) -> list[RuleMatch]:
        """Find excessive blank lines (3+ consecutive)."""
        matches = []
        for m in re.finditer(r'\n{3,}', text):
            num_blanks = len(m.group()) - 1
            matches.append(RuleMatch(
                rule_id="multiple-blank-lines",
                rule_name="Multiple Blank Lines",
                category="formatting",
                severity="low",
                text=f"{num_blanks} consecutive blank lines",
                suggestion="Reduce to single blank line",
                location=f"Line {self._get_line_number(text, m.start())}",
                context="Excessive vertical spacing",
            ))
        return matches

    def _check_inconsistent_quotes(self, text: str) -> list[RuleMatch]:
        """Check for mix of straight and curly quotes."""
        matches = []
        straight_double = text.count('"')
        curly_double = text.count('"') + text.count('"')
        straight_single = text.count("'")
        curly_single = text.count(''') + text.count(''')

        if straight_double > 0 and curly_double > 0:
            matches.append(RuleMatch(
                rule_id="inconsistent-quotes",
                rule_name="Inconsistent Double Quotes",
                category="formatting",
                severity="low",
                text=f'Mix of " ({straight_double}) and ""/\"\" ({curly_double})',
                suggestion="Use consistent quote style throughout",
                location="Document-wide",
                context="Consider using curly quotes for published documents",
            ))

        if straight_single > 0 and curly_single > 0:
            # Only flag if there are significant numbers of both (apostrophes are common)
            if straight_single > 3 and curly_single > 3:
                matches.append(RuleMatch(
                    rule_id="inconsistent-quotes",
                    rule_name="Inconsistent Single Quotes/Apostrophes",
                    category="formatting",
                    severity="low",
                    text=f"Mix of ' ({straight_single}) and ''/'` ({curly_single})",
                    suggestion="Use consistent apostrophe style",
                    location="Document-wide",
                    context="May indicate copy-paste from different sources",
                ))
        return matches

    def _check_tab_characters(self, text: str) -> list[RuleMatch]:
        """Find tab characters (often from copy-paste)."""
        matches = []
        tab_count = text.count('\t')

        if tab_count > 0:
            matches.append(RuleMatch(
                rule_id="tab-characters",
                rule_name="Tab Characters",
                category="formatting",
                severity="low",
                text=f"{tab_count} tab character(s)",
                suggestion="Replace tabs with spaces for consistent formatting",
                location="Multiple locations",
                context="Tabs may render inconsistently across applications",
            ))
        return matches

    def _check_double_hyphen_emdash(self, text: str) -> list[RuleMatch]:
        """Find -- that should probably be em-dash (—)."""
        matches = []
        for m in re.finditer(r'(\w)\s*--\s*(\w)', text):
            matches.append(RuleMatch(
                rule_id="double-hyphen-emdash",
                rule_name="Double Hyphen Instead of Em-Dash",
                category="formatting",
                severity="low",
                text=m.group(),
                suggestion=f"{m.group(1)}—{m.group(2)}",
                location=f"Line {self._get_line_number(text, m.start())}",
                context=self._get_context(text, m.start(), m.end()),
            ))
        return matches

    # === LOWER PRIORITY CHECKS ===

    def _check_hidden_characters(self, text: str) -> list[RuleMatch]:
        """Find zero-width and other hidden characters."""
        matches = []
        hidden_chars = {
            '\u200b': 'zero-width space',
            '\u200c': 'zero-width non-joiner',
            '\u200d': 'zero-width joiner',
            '\ufeff': 'byte order mark',
            '\u00a0': 'non-breaking space',
            '\u2060': 'word joiner',
        }

        found = {}
        for char, name in hidden_chars.items():
            count = text.count(char)
            if count > 0:
                found[name] = count

        if found:
            details = ", ".join(f"{name}: {count}" for name, count in found.items())
            matches.append(RuleMatch(
                rule_id="hidden-characters",
                rule_name="Hidden Characters",
                category="formatting",
                severity="medium",
                text=f"Found hidden characters",
                suggestion="Remove hidden characters that may cause display issues",
                location="Document-wide",
                context=details,
            ))
        return matches

    def _check_straight_vs_curly_quotes(self, text: str) -> list[RuleMatch]:
        """Flag if document uses only straight quotes (might want curly for publishing)."""
        matches = []
        straight_quotes = text.count('"') + text.count("'")
        curly_quotes = text.count('"') + text.count('"') + text.count(''') + text.count(''')

        # Only flag if there are many straight quotes and zero curly
        if straight_quotes > 10 and curly_quotes == 0:
            matches.append(RuleMatch(
                rule_id="straight-vs-curly-quotes",
                rule_name="Straight Quotes Only",
                category="formatting",
                severity="low",
                text=f"{straight_quotes} straight quotes",
                suggestion="Consider using curly quotes for professional documents",
                location="Document-wide",
                context="Straight quotes are fine for code/technical docs",
            ))
        return matches


def rule_match_to_dict(match: RuleMatch) -> dict:
    """Convert RuleMatch to dict for JSON serialization."""
    return {
        "rule_id": match.rule_id,
        "rule_name": match.rule_name,
        "category": match.category,
        "severity": match.severity,
        "text": match.text,
        "suggestion": match.suggestion,
        "location": match.location,
        "context": match.context,
        "source": "rule",  # Distinguish from LLM-detected issues
    }
