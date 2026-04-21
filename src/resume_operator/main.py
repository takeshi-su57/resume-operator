"""CLI entry point for resume-operator."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
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


def _validate_resume(resume: Path) -> None:
    """Validate resume file exists and is a PDF."""
    if not resume.exists() or not resume.is_file():
        raise typer.BadParameter(f"'{resume}' does not exist or is not a file.")
    if resume.suffix.lower() != ".pdf":
        raise typer.BadParameter(f"'{resume}' is not a PDF file (expected .pdf extension).")


def _validate_master(master: Path) -> None:
    """Validate master YAML exists and has a YAML extension."""
    if not master.exists() or not master.is_file():
        raise typer.BadParameter(f"'{master}' does not exist or is not a file.")
    if master.suffix.lower() not in {".yaml", ".yml"}:
        raise typer.BadParameter(f"'{master}' is not a YAML file (expected .yaml or .yml).")


def _validate_facts(facts: Path) -> None:
    """Validate facts bank YAML if provided (optional file)."""
    if not facts.exists() or not facts.is_file():
        raise typer.BadParameter(f"'{facts}' does not exist or is not a file.")
    if facts.suffix.lower() not in {".yaml", ".yml"}:
        raise typer.BadParameter(f"'{facts}' is not a YAML file (expected .yaml or .yml).")


DEFAULT_FACTS_PATH = Path("data/facts_bank.yaml")


def _validate_job(job: Path) -> None:
    """Validate job description file exists and is readable."""
    if not job.exists() or not job.is_file():
        raise typer.BadParameter(f"'{job}' does not exist or is not a file.")


def _score_color(score: float) -> str:
    """Return Rich color tag based on ATS score value."""
    if score >= 0.7:
        return "green"
    if score >= 0.4:
        return "yellow"
    return "red"


@app.command()
def run(
    master: Path = typer.Option(
        None, "--master", "-m", help="Path to master_resume.yaml (preferred)"
    ),
    resume: Path = typer.Option(
        None, "--resume", "-r", help="Path to resume PDF (legacy — use --master instead)"
    ),
    facts: Path = typer.Option(
        None,
        "--facts",
        "-f",
        help=f"Path to facts_bank.yaml (optional; defaults to {DEFAULT_FACTS_PATH} if it exists)",
    ),
    job: Path = typer.Option(..., "--job", "-j", help="Path to job description text file"),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            "Parent directory for per-application output folders "
            "(default: data/applications/). Each run creates "
            "{parent}/{YYYY-MM-DD}_{slug}/ — never overwrites prior runs."
        ),
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate inputs without executing"),
) -> None:
    """Run the full resume optimization pipeline."""
    _setup_logging(verbose)
    if master is None and resume is None:
        raise typer.BadParameter("Provide either --master (preferred) or --resume.")
    if master is not None and resume is not None:
        raise typer.BadParameter("Use --master or --resume, not both.")

    if master is not None:
        _validate_master(master)
    else:
        _validate_resume(resume)
    _validate_job(job)

    # Facts bank is optional: explicit --facts is validated; fall back to the
    # default path only if it actually exists on disk.
    resolved_facts: Path | None = None
    if facts is not None:
        _validate_facts(facts)
        resolved_facts = facts
    elif DEFAULT_FACTS_PATH.exists():
        resolved_facts = DEFAULT_FACTS_PATH

    if dry_run:
        source_line = (
            f"[bold]Master:[/bold] {master}" if master else f"[bold]Resume:[/bold] {resume}"
        )
        facts_line = f"\n[bold]Facts:[/bold] {resolved_facts}" if resolved_facts else ""
        parent_line = f"\n[bold]Output parent:[/bold] {output or 'data/applications/'}"
        console.print(
            Panel(
                f"{source_line}{facts_line}\n[bold]Job description:[/bold] {job}{parent_line}",
                title="Dry run — inputs validated",
                border_style="green",
            )
        )
        return

    # Reserve a per-application output folder before invoking the graph.
    from resume_operator.tools.output_dir import resolve_output_dir

    jd_text = job.read_text(encoding="utf-8") if job.exists() else ""
    output_dir = resolve_output_dir(parent=output, jd_path=job, jd_text=jd_text)

    initial: dict[str, str] = {
        "job_description_path": str(job),
        "output_dir": str(output_dir),
        "output_path": str(output_dir / "resume.pdf"),
    }
    if master is not None:
        initial["master_path"] = str(master)
    else:
        initial["resume_path"] = str(resume)
    if resolved_facts is not None:
        initial["facts_path"] = str(resolved_facts)

    graph = build_graph()
    with Status("[bold cyan]Running optimization pipeline...", console=console):
        result = graph.invoke(initial)

    errors: list[str] = result.get("errors", [])
    if errors:
        error_text = "\n".join(f"• {e}" for e in errors)
        console.print(Panel(error_text, title="Errors", border_style="red"))

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
    _validate_resume(resume)

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
def bootstrap(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume PDF"),
    output: Path = typer.Option(
        Path("data/master_resume.yaml"), "--output", "-o", help="Output master_resume.yaml path"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """One-time: parse a resume PDF via LLM and write a hand-editable `master_resume.yaml`.

    This is the only command that calls the LLM to ingest a resume. From then on,
    `run --master` uses the YAML directly.
    """
    from resume_operator.tools.master_resume import resume_data_to_master, save_master

    _setup_logging(verbose)
    _validate_resume(resume)

    graph = build_graph()
    with Status("[bold cyan]Bootstrapping master resume from PDF...", console=console):
        result = graph.invoke({"resume_path": str(resume)})

    errors: list[str] = result.get("errors", [])
    if errors:
        for error in errors:
            console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1)

    resume_data: ResumeData = result["resume"]
    master = resume_data_to_master(resume_data)
    save_master(master, output)

    console.print(
        Panel(
            f"[bold]Wrote:[/bold] {output}\n"
            f"[bold]Experience entries:[/bold] {len(master.experience)}\n"
            f"[bold]Education entries:[/bold] {len(master.education)}\n"
            f"[bold]Skills:[/bold] {len(master.skills)}\n\n"
            f"[yellow]Review the YAML, edit freely, and keep it under version control.[/yellow]",
            title="Master resume bootstrapped",
            border_style="green",
        )
    )


@app.command()
def score(
    master: Path = typer.Option(
        None, "--master", "-m", help="Path to master_resume.yaml (preferred)"
    ),
    resume: Path = typer.Option(None, "--resume", "-r", help="Path to resume PDF (legacy)"),
    job: Path = typer.Option(..., "--job", "-j", help="Path to job description text file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Score resume ATS compatibility against a job description."""
    _setup_logging(verbose)
    if master is None and resume is None:
        raise typer.BadParameter("Provide either --master (preferred) or --resume.")
    if master is not None and resume is not None:
        raise typer.BadParameter("Use --master or --resume, not both.")
    if master is not None:
        _validate_master(master)
    else:
        _validate_resume(resume)
    _validate_job(job)

    initial: dict[str, str] = {"job_description_path": str(job)}
    if master is not None:
        initial["master_path"] = str(master)
    else:
        initial["resume_path"] = str(resume)

    graph = build_score_graph()
    with Status("[bold cyan]Scoring resume...", console=console):
        result = graph.invoke(initial)

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
