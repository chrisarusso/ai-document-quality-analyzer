"""Command-line interface for Document Quality Analyzer."""

import argparse
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from .analyzers.quality_analyzer import QualityAnalyzer
from .analyzers.llm_analyzer import LLMProvider
from .integrations.slack import SlackNotifier
from .models import IssueSeverity


console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Document Quality Analyzer - LLM-powered document review"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a document")
    analyze_parser.add_argument("url", help="Google Docs/Slides URL")
    analyze_parser.add_argument(
        "--provider", "-p",
        choices=["openai", "anthropic", "google"],
        default="openai",
        help="LLM provider to use"
    )
    analyze_parser.add_argument(
        "--type", "-t",
        choices=["proposal", "kickoff"],
        help="Document type (auto-detected if not specified)"
    )
    analyze_parser.add_argument(
        "--slack", "-s",
        action="store_true",
        help="Post results to Slack"
    )
    analyze_parser.add_argument(
        "--comment", "-c",
        action="store_true",
        help="Add comments to the document"
    )

    # compare command (compare all 3 providers)
    compare_parser = subparsers.add_parser("compare", help="Compare all 3 LLM providers")
    compare_parser.add_argument("url", help="Google Docs/Slides URL")

    # transcript command
    transcript_parser = subparsers.add_parser("transcript", help="Analyze a call transcript")
    transcript_parser.add_argument("file", help="Transcript file path or '-' for stdin")
    transcript_parser.add_argument(
        "--sales", "-s",
        action="store_true",
        help="Analyze as sales call (BANNT scoring)"
    )
    transcript_parser.add_argument(
        "--provider", "-p",
        choices=["openai", "anthropic", "google"],
        default="openai",
        help="LLM provider to use"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "analyze":
        analyze_document(args)
    elif args.command == "compare":
        compare_providers(args)
    elif args.command == "transcript":
        analyze_transcript(args)


def analyze_document(args):
    """Analyze a single document."""
    console.print(f"\n[bold blue]Analyzing document...[/bold blue]")
    console.print(f"URL: {args.url}")
    console.print(f"Provider: {args.provider}\n")

    try:
        analyzer = QualityAnalyzer(provider=args.provider)
        result = analyzer.analyze_url(args.url)

        # Display results
        display_result(result)

        # Post to Slack if requested
        if args.slack:
            console.print("\n[bold]Posting to Slack...[/bold]")
            notifier = SlackNotifier()
            slack_result = notifier.post_analysis(result)
            if slack_result.get("success"):
                console.print(f"[green]Posted to Slack[/green]")
            else:
                console.print(f"[red]Slack error: {slack_result.get('error')}[/red]")

        # Add comments if requested
        if args.comment:
            console.print("\n[bold]Adding comments to document...[/bold]")
            add_document_comments(analyzer, args.url, result)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


def compare_providers(args):
    """Compare all 3 LLM providers on the same document."""
    console.print(f"\n[bold blue]Comparing LLM providers...[/bold blue]")
    console.print(f"URL: {args.url}\n")

    results = {}
    for provider in ["openai", "anthropic", "google"]:
        console.print(f"[dim]Analyzing with {provider}...[/dim]")
        try:
            analyzer = QualityAnalyzer(provider=provider)
            results[provider] = analyzer.analyze_url(args.url)
        except Exception as e:
            console.print(f"[red]{provider} failed: {e}[/red]")
            results[provider] = None

    # Display comparison
    display_comparison(results)


def analyze_transcript(args):
    """Analyze a call transcript."""
    # Read transcript
    if args.file == "-":
        transcript = sys.stdin.read()
    else:
        with open(args.file) as f:
            transcript = f.read()

    console.print(f"\n[bold blue]Analyzing transcript...[/bold blue]")
    console.print(f"Type: {'Sales (BANNT)' if args.sales else 'Client Call'}")
    console.print(f"Provider: {args.provider}\n")

    try:
        analyzer = QualityAnalyzer(provider=args.provider)
        result = analyzer.analyze_transcript(
            transcript,
            is_sales_call=args.sales,
            title=args.file if args.file != "-" else "Transcript"
        )

        display_result(result)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


def display_result(result):
    """Display analysis result."""
    # Header
    console.print(Panel(
        f"[bold]{result.document_title}[/bold]\n"
        f"Type: {result.document_type.value}\n"
        f"Analyzed by: {result.llm_provider}",
        title="Document Analysis"
    ))

    # Score
    if result.score:
        score = result.score.overall
        color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
        console.print(f"\n[bold]Score: [{color}]{score}/100[/{color}][/bold]")

        table = Table(title="Score Breakdown")
        table.add_column("Category")
        table.add_column("Score", justify="right")
        table.add_row("Spelling/Grammar", f"{result.score.spelling_grammar}/100")
        table.add_row("Required Content", f"{result.score.required_content}/100")
        table.add_row("Math Accuracy", f"{result.score.math_accuracy}/100")
        console.print(table)

    # BANNT Score
    if result.bannt_score:
        bannt = result.bannt_score
        console.print(f"\n[bold]BANNT Score: {bannt.score}/5[/bold]")

        table = Table(title="BANNT Breakdown")
        table.add_column("Element")
        table.add_column("Status")
        table.add_column("Notes")
        table.add_row("Budget", "✅" if bannt.budget else "❌", bannt.budget_notes or "-")
        table.add_row("Authority", "✅" if bannt.authority else "❌", bannt.authority_notes or "-")
        table.add_row("Need", "✅" if bannt.need else "❌", bannt.need_notes or "-")
        table.add_row("Next Steps", "✅" if bannt.next_steps else "❌", bannt.next_steps_notes or "-")
        table.add_row("Timeline", "✅" if bannt.timeline else "❌", bannt.timeline_notes or "-")
        console.print(table)

    # Issues
    if result.issues:
        console.print(f"\n[bold]Issues Found: {len(result.issues)}[/bold]")

        # Group by severity
        for severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW, IssueSeverity.INFO]:
            severity_issues = [i for i in result.issues if i.severity == severity]
            if not severity_issues:
                continue

            icon = {
                IssueSeverity.CRITICAL: "🔴",
                IssueSeverity.HIGH: "🟠",
                IssueSeverity.MEDIUM: "🟡",
                IssueSeverity.LOW: "⚪",
                IssueSeverity.INFO: "ℹ️",
            }[severity]

            console.print(f"\n{icon} [bold]{severity.value.upper()}[/bold] ({len(severity_issues)})")

            for issue in severity_issues[:5]:  # Limit display
                console.print(f"  • {issue.category.value}: {issue.title}")
                if issue.suggestion:
                    console.print(f"    → {issue.suggestion}")

            if len(severity_issues) > 5:
                console.print(f"  [dim]... and {len(severity_issues) - 5} more[/dim]")

    console.print()


def display_comparison(results):
    """Display comparison of multiple providers."""
    table = Table(title="Provider Comparison")
    table.add_column("Metric")
    for provider in results:
        table.add_column(provider.title())

    # Score row
    scores = []
    for provider, result in results.items():
        if result and result.score:
            scores.append(f"{result.score.overall}/100")
        else:
            scores.append("Error")
    table.add_row("Overall Score", *scores)

    # Issues count row
    issues = []
    for provider, result in results.items():
        if result:
            issues.append(str(len(result.issues)))
        else:
            issues.append("-")
    table.add_row("Issues Found", *issues)

    # Spelling/grammar issues
    sg_issues = []
    for provider, result in results.items():
        if result:
            count = sum(1 for i in result.issues if i.category.value in ["spelling", "grammar", "spacing"])
            sg_issues.append(str(count))
        else:
            sg_issues.append("-")
    table.add_row("Spelling/Grammar", *sg_issues)

    console.print(table)


def add_document_comments(analyzer, url, result):
    """Add comments to document for each issue."""
    extractor = analyzer.slides_extractor if "/presentation/" in url else analyzer.docs_extractor

    # Build comment content
    comment_lines = ["[Document Quality Analyzer]", ""]

    for issue in result.issues[:20]:  # Limit comments
        severity_icon = {
            IssueSeverity.CRITICAL: "🔴",
            IssueSeverity.HIGH: "🟠",
            IssueSeverity.MEDIUM: "🟡",
            IssueSeverity.LOW: "⚪",
            IssueSeverity.INFO: "ℹ️",
        }[issue.severity]

        line = f"{severity_icon} {issue.category.value}: {issue.title}"
        if issue.location:
            line += f" ({issue.location})"
        comment_lines.append(line)

        if issue.suggestion:
            comment_lines.append(f"   → {issue.suggestion}")
        comment_lines.append("")

    if len(result.issues) > 20:
        comment_lines.append(f"... and {len(result.issues) - 20} more issues")

    # Add as single comment
    comment_result = extractor.add_comment(url, "\n".join(comment_lines))
    if comment_result.get("success"):
        console.print(f"[green]Added comment with {min(len(result.issues), 20)} issues[/green]")
    else:
        console.print(f"[red]Failed to add comment: {comment_result.get('error')}[/red]")


if __name__ == "__main__":
    main()
