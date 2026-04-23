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


def _should_offer_enrich(
    result: dict[str, object],
    *,
    no_enrich: bool,
    master_path: Path | None,
) -> bool:
    """Decide whether to offer an interactive enrichment session.

    Triggers when:
      - the user hasn't explicitly disabled it via `--no-enrich`
      - we're running with a master YAML (the only path that supports a
        meaningful enrichment loop — the legacy PDF path is deprecated)
      - stdin is a TTY (so we can actually prompt the user)
      - the optimization actually ran (wasn't skipped due to high ATS score)
      - the tailor came back thin: kept+reworded items below `enrich_threshold`
    """
    import sys

    if no_enrich or master_path is None or not sys.stdin.isatty():
        return False

    report = result.get("report", {})
    if isinstance(report, dict) and report.get("optimization_skipped"):
        return False

    from resume_operator.state import TailoredResume

    tailored = result.get("tailored_resume")
    if not isinstance(tailored, TailoredResume) or not tailored.items:
        return False

    threshold = get_settings().enrich_threshold
    return len(tailored.kept_or_reworded()) < threshold


def _run_auto_enrich(*, master_path: Path, facts_path: Path | None, jd_text: str) -> bool:
    """Pause the pipeline, prompt for an enrichment session, persist accepted items.

    Returns True if any items were appended to the facts bank (so the caller
    knows to re-invoke the graph), False otherwise.
    """
    from rich.prompt import Prompt

    from resume_operator.state import FactsBank
    from resume_operator.tools.enrich import (
        assemble_additions,
        collect_existing_ids,
        run_interactive_session,
    )
    from resume_operator.tools.facts_bank import append_to_facts, load_facts
    from resume_operator.tools.master_resume import load_master

    console.print(
        Panel(
            "Only a few items landed in the tailored resume — your master + "
            "facts may be thin for this JD. We can grow your facts bank with "
            "a short interview now (LLM asks grounded questions, you answer "
            "in your own words, LLM polishes the phrasing).",
            title="Enrichment available",
            border_style="yellow",
        )
    )
    if Prompt.ask("Start an enrichment session?", choices=["y", "n"], default="y") != "y":
        return False

    target_facts = facts_path or DEFAULT_FACTS_PATH
    master_obj = load_master(master_path)
    facts_obj = load_facts(target_facts) if target_facts.exists() else FactsBank()

    plan = run_interactive_session(master_obj, facts_obj, jd_text, console=console)
    if not plan.items:
        console.print("[yellow]No items accepted — facts_bank unchanged.[/yellow]")
        return False

    existing_ids = collect_existing_ids(facts_obj)
    projects, extra_bullets, skills, certifications = assemble_additions(
        plan, existing_ids=existing_ids
    )
    append_to_facts(
        target_facts,
        projects=projects,
        extra_bullets=extra_bullets,
        skills=skills,
        certifications=certifications,
    )
    console.print(
        Panel(
            f"[bold]Wrote:[/bold] {target_facts}\n"
            f"Projects: +{len(projects)}  |  Extra bullets: +{len(extra_bullets)}  |  "
            f"Skills: +{len(skills)}  |  Certs: +{len(certifications)}",
            title="Facts bank updated",
            border_style="green",
        )
    )
    return True


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
    no_enrich: bool = typer.Option(
        False,
        "--no-enrich",
        help=(
            "Skip the auto-enrich interview even if the first tailor pass is thin. "
            "Use for scripted / headless runs where stdin isn't available."
        ),
    ),
    style: Path = typer.Option(
        None,
        "--style",
        "-s",
        help=(
            "Path to a StyleTemplate YAML (#72). Overrides RESUME_STYLE_PATH env. "
            "If neither set, falls back to input/style.default.yaml when it exists."
        ),
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate inputs without executing"),
) -> None:
    """Run the full resume optimization pipeline.

    If the first tailoring pass keeps fewer items than the configured
    `enrich_threshold` (default 6), the CLI offers an interactive interview
    to grow `facts_bank.yaml`, then re-runs the graph once with the richer
    inputs. Pass `--no-enrich` to skip that step entirely.
    """
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
    if style is not None:
        if not style.exists():
            raise typer.BadParameter(f"--style path {style} does not exist.")
        initial["style_path"] = str(style)

    graph = build_graph()
    with Status("[bold cyan]Running optimization pipeline...", console=console):
        result = graph.invoke(initial)

    # --- Auto-enrich: if the first tailor pass is thin, offer an interview ---
    if _should_offer_enrich(result, no_enrich=no_enrich, master_path=master):
        if _run_auto_enrich(
            master_path=master,
            facts_path=resolved_facts,
            jd_text=jd_text,
        ):
            # New items landed in facts_bank.yaml; re-invoke the graph so
            # load_master → optimize_content picks them up.
            console.print("[cyan]Re-running optimization with enriched facts...[/cyan]")
            if resolved_facts is None:
                # `run_auto_enrich` created data/facts_bank.yaml if it wasn't there.
                resolved_facts = DEFAULT_FACTS_PATH
                initial["facts_path"] = str(resolved_facts)
            with Status("[bold cyan]Re-running pipeline...", console=console):
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
    no_interview: bool = typer.Option(
        False,
        "--no-interview",
        help=(
            "Skip the post-parse interview that asks for missing senior-format "
            "fields (headline, links, per-role tech, skill groups). Useful for "
            "scripted or CI runs."
        ),
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """One-time: parse a resume PDF via LLM and write a hand-editable `master_resume.yaml`.

    After the LLM parse, walks an interactive interview asking for any
    senior-format fields the source PDF didn't carry (headline, Portfolio /
    LinkedIn / GitHub URLs, per-role tech stacks, categorised skill groups).
    Pass `--no-interview` to skip the interview entirely.
    """
    from resume_operator.nodes.parse_resume import parse_resume as parse_resume_node
    from resume_operator.state import ResumeMaster, ResumeOptimizerState
    from resume_operator.tools.bootstrap_interview import run_interview, should_run_interview
    from resume_operator.tools.master_resume import save_master

    _setup_logging(verbose)
    _validate_resume(resume)

    # Bootstrap only needs the parse_resume node — not the full graph. Invoking the
    # graph here used to fire ats_score + analyze_gaps + optimize_content +
    # generate_pdf + report_results as well, which wasted three extra LLM calls
    # plus a PDF render on every bootstrap (issue #60).
    with Status("[bold cyan]Bootstrapping master resume from PDF...", console=console):
        state = ResumeOptimizerState(resume_path=str(resume))
        result = parse_resume_node(state)

    errors: list[str] = result.get("errors", [])
    if errors:
        for error in errors:
            console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1)

    master: ResumeMaster = result["master"]

    # Interactive post-parse interview (#70) — fill in the senior-format fields
    # the LLM couldn't extract from the source PDF (URLs, per-role tech, skill
    # groupings, fallback headline).
    if should_run_interview(no_interview=no_interview):
        master = run_interview(master, console=console)

    save_master(master, output)

    headline_status = "set" if master.headline else "empty (tailor writes one per JD)"
    console.print(
        Panel(
            f"[bold]Wrote:[/bold] {output}\n"
            f"[bold]Experience entries:[/bold] {len(master.experience)}\n"
            f"[bold]Education entries:[/bold] {len(master.education)}\n"
            f"[bold]Skills:[/bold] {len(master.all_skills())}\n"
            f"[bold]Links:[/bold] {len(master.links)}\n"
            f"[bold]Headline:[/bold] {headline_status}\n\n"
            f"[yellow]Review the YAML, edit freely, and keep it under version control.[/yellow]",
            title="Master resume bootstrapped",
            border_style="green",
        )
    )


@app.command(name="extract-style")
def extract_style(
    from_: Path = typer.Option(
        ..., "--from", "-i", help="Path to a reference .docx (resume or CV template)"
    ),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Where to write the derived style.yaml"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Derive a StyleTemplate YAML from a reference .docx (issue #72).

    Reads the document's named styles (Normal, Heading, Heading 2, …), section
    margins, and default font family; writes a StyleTemplate YAML mirroring
    those choices. Every field is a starting point — review and hand-tweak the
    saved file afterwards.

    Then apply with:
        resume-operator run --master M.yaml --job J.txt --style <output>
    """
    from resume_operator.tools.style import save_style
    from resume_operator.tools.style_from_docx import (
        StyleExtractionError,
        extract_style_from_docx,
    )

    _setup_logging(verbose)
    if not from_.exists() or not from_.is_file():
        raise typer.BadParameter(f"'{from_}' does not exist or is not a file.")
    if from_.suffix.lower() != ".docx":
        raise typer.BadParameter(f"'{from_}' is not a .docx file.")

    with Status("[bold cyan]Extracting style...", console=console):
        try:
            template = extract_style_from_docx(from_)
        except StyleExtractionError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc

    save_style(template, output)
    console.print(
        Panel(
            f"[bold]Wrote:[/bold] {output}\n"
            f"[bold]Font family:[/bold] {template.font_family}\n"
            f"[bold]Margins:[/bold] "
            f"{template.margins.top}in top / "
            f"{template.margins.bottom}in bottom / "
            f"{template.margins.side}in side\n"
            f"[bold]Name size:[/bold] {template.name_style.size}pt  "
            f"[bold]Section size:[/bold] {template.section.size}pt  "
            f"[bold]Body size:[/bold] {template.body.size}pt\n\n"
            f"[yellow]Review the YAML, tweak as needed. Apply via:[/yellow]\n"
            f"  resume-operator run --master ... --job ... --style {output}",
            title="Style extracted",
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
