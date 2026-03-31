"""CLI entry point for resume-operator."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.status import Status

from resume_operator.config import get_settings
from resume_operator.graph import build_graph, build_score_graph
from resume_operator.state import ATSScore, GapAnalysis, OptimizedResume, ResumeData

app = typer.Typer(
    name="resume-operator",
    help="Resume Optimizer AI Agent — tailor your resume to any job description.",
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    """Configure logging from config.log_level, overridden by --verbose."""
    if verbose:
        level = logging.DEBUG
    else:
        level_name = get_settings().log_level.upper()
        level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _score_color(score: float) -> str:
    """Return Rich color tag based on ATS score value."""
    if score >= 0.7:
        return "green"
    if score >= 0.4:
        return "yellow"
    return "red"


@app.command()
def run(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
    job: Path = typer.Option(..., "--job", "-j", help="Path to job description text file"),
    output: Path = typer.Option(
        Path("data/optimized_resume.pdf"), "--output", "-o", help="Output PDF path"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Run the full resume optimization pipeline."""
    _setup_logging(verbose)

    if not resume.exists() or not resume.is_file():
        console.print(f"[red]Error: '{resume}' does not exist or is not a file.[/red]")
        raise typer.Exit(code=1)

    if not job.exists() or not job.is_file():
        console.print(f"[red]Error: '{job}' does not exist or is not a file.[/red]")
        raise typer.Exit(code=1)

    graph = build_graph()
    with Status("[bold cyan]Running optimization pipeline...", console=console):
        result = graph.invoke(
            {
                "resume_path": str(resume),
                "job_description_path": str(job),
                "output_path": str(output),
            }
        )

    errors: list[str] = result.get("errors", [])
    if errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")

    # Display resume data
    resume_data: ResumeData = result.get("resume", ResumeData())
    if resume_data.name:
        console.print("\n[bold green]Parsed Resume:[/bold green]")
        console.print(f"  Name: {resume_data.name}")
        console.print(f"  Email: {resume_data.email}")
        console.print(f"  Skills: {', '.join(resume_data.skills)}")

    # Display ATS score with color coding
    ats: ATSScore = result.get("ats_score", ATSScore())
    if ats.score > 0:
        color = _score_color(ats.score)
        console.print(f"\n[bold green]ATS Score:[/bold green] [{color}]{ats.score:.0%}[/{color}]")
        console.print(f"  Reasoning: {ats.reasoning}")
        if ats.keyword_matches:
            console.print(f"  [green]Matches:[/green] {', '.join(ats.keyword_matches)}")
        if ats.keyword_gaps:
            console.print(f"  [yellow]Gaps:[/yellow] {', '.join(ats.keyword_gaps)}")

    # Display gap analysis
    gaps: GapAnalysis = result.get("gap_analysis", GapAnalysis())
    if gaps.gaps or gaps.strengths or gaps.suggestions:
        console.print("\n[bold green]Gap Analysis:[/bold green]")
        if gaps.strengths:
            console.print("  [green]Strengths:[/green]")
            for s in gaps.strengths:
                console.print(f"    ✓ {s}")
        if gaps.gaps:
            console.print("  [yellow]Gaps:[/yellow]")
            for g in gaps.gaps:
                console.print(f"    ✗ {g}")
        if gaps.suggestions:
            console.print("  [cyan]Suggestions:[/cyan]")
            for s in gaps.suggestions:
                console.print(f"    → {s}")

    # Display optimization changes
    optimized: OptimizedResume = result.get("optimized_resume", OptimizedResume())
    if optimized.changes_made:
        console.print("\n[bold green]Optimization Changes:[/bold green]")
        for change in optimized.changes_made:
            console.print(f"  → {change}")

    # Display output path
    output_result: str = result.get("output_path", "")
    if output_result:
        console.print(f"\n[bold green]Output PDF:[/bold green] {output_result}")

    if not errors:
        console.print("\n[bold green]Pipeline completed successfully.[/bold green]")


@app.command(name="parse-resume")
def parse_resume(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Parse a resume PDF and display extracted data."""
    _setup_logging(verbose)

    if not resume.exists() or not resume.is_file():
        console.print(f"[red]Error: '{resume}' does not exist or is not a file.[/red]")
        raise typer.Exit(code=1)

    graph = build_graph()
    with Status("[bold cyan]Parsing resume...", console=console):
        result = graph.invoke({"resume_path": str(resume)})

    errors: list[str] = result.get("errors", [])
    if errors:
        for error in errors:
            console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1)

    resume_data: ResumeData = result["resume"]
    console.print(f"[bold green]Name:[/bold green] {resume_data.name}")
    console.print(f"[bold green]Email:[/bold green] {resume_data.email}")
    console.print(f"[bold green]Phone:[/bold green] {resume_data.phone}")
    console.print(f"[bold green]Skills:[/bold green] {', '.join(resume_data.skills)}")
    console.print(f"[bold green]Experience:[/bold green] {len(resume_data.experience)} entries")
    console.print(f"[bold green]Education:[/bold green] {len(resume_data.education)} entries")
    console.print(
        f"[bold green]Certifications:[/bold green] {len(resume_data.certifications)} entries"
    )


@app.command()
def score(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
    job: Path = typer.Option(..., "--job", "-j", help="Path to job description text file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Score resume ATS compatibility against a job description."""
    _setup_logging(verbose)

    if not resume.exists() or not resume.is_file():
        console.print(f"[red]Error: '{resume}' does not exist or is not a file.[/red]")
        raise typer.Exit(code=1)

    if not job.exists() or not job.is_file():
        console.print(f"[red]Error: '{job}' does not exist or is not a file.[/red]")
        raise typer.Exit(code=1)

    graph = build_score_graph()
    with Status("[bold cyan]Scoring resume...", console=console):
        result = graph.invoke(
            {
                "resume_path": str(resume),
                "job_description_path": str(job),
            }
        )

    errors: list[str] = result.get("errors", [])
    if errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")

    ats: ATSScore = result.get("ats_score", ATSScore())
    if ats.score > 0:
        color = _score_color(ats.score)
        console.print(f"\n[bold green]ATS Score:[/bold green] [{color}]{ats.score:.0%}[/{color}]")
        console.print(f"  Reasoning: {ats.reasoning}")
        if ats.keyword_matches:
            console.print(f"  [green]Matches:[/green] {', '.join(ats.keyword_matches)}")
        if ats.keyword_gaps:
            console.print(f"  [yellow]Gaps:[/yellow] {', '.join(ats.keyword_gaps)}")
    elif not errors:
        console.print("[yellow]No ATS score produced.[/yellow]")


if __name__ == "__main__":
    app()
