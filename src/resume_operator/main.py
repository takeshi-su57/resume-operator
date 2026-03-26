"""CLI entry point for resume-operator."""

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="resume-operator",
    help="Resume Optimizer AI Agent — tailor your resume to any job description.",
)
console = Console()


@app.command()
def run(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
    job: Path = typer.Option(..., "--job", "-j", help="Path to job description text file"),
    output: Path = typer.Option(
        Path("data/optimized_resume.pdf"), "--output", "-o", help="Output PDF path"
    ),
) -> None:
    """Run the full resume optimization pipeline."""
    # TODO: Build and invoke the LangGraph pipeline
    console.print(f"[bold]Resume:[/bold] {resume}")
    console.print(f"[bold]Job description:[/bold] {job}")
    console.print(f"[bold]Output:[/bold] {output}")
    console.print("[yellow]Not implemented yet.[/yellow]")


@app.command(name="parse-resume")
def parse_resume(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
) -> None:
    """Parse a resume PDF and display extracted data."""
    # TODO: Call parse_resume node and display results
    console.print(f"[bold]Resume:[/bold] {resume}")
    console.print("[yellow]Not implemented yet.[/yellow]")


@app.command()
def score(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
    job: Path = typer.Option(..., "--job", "-j", help="Path to job description text file"),
) -> None:
    """Score resume ATS compatibility against a job description."""
    # TODO: Run parse_resume + ats_score nodes and display results
    console.print(f"[bold]Resume:[/bold] {resume}")
    console.print(f"[bold]Job description:[/bold] {job}")
    console.print("[yellow]Not implemented yet.[/yellow]")


if __name__ == "__main__":
    app()
