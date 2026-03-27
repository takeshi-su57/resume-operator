"""CLI entry point for resume-operator."""

from pathlib import Path

import typer
from rich.console import Console
from rich.status import Status

from resume_operator.graph import build_graph
from resume_operator.state import ResumeData

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
) -> None:
    """Score resume ATS compatibility against a job description."""
    # TODO: Run parse_resume + ats_score nodes and display results
    console.print(f"[bold]Resume:[/bold] {resume}")
    console.print(f"[bold]Job description:[/bold] {job}")
    console.print("[yellow]Not implemented yet.[/yellow]")


if __name__ == "__main__":
    app()
