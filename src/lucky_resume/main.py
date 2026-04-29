"""CLI entry point for lucky-resume."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from lucky_resume.config import get_settings
from lucky_resume.flows.approval import run_approval_loop
from lucky_resume.flows.enrich import DEFAULT_FACTS_PATH, run_auto_enrich
from lucky_resume.graph import (
    build_finalize_graph,
    build_graph,
    build_score_graph,
    build_tailor_graph,
)
from lucky_resume.prompters import RichPrompter
from lucky_resume.state import (
    ATSScore,
    GapAnalysis,
    OptimizedResume,
    ResumeData,
)
from lucky_resume.tools.builtin_styles import is_builtin_identifier

app = typer.Typer(
    name="lucky-resume",
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

    from lucky_resume.state import TailoredResume

    tailored = result.get("tailored_resume")
    if not isinstance(tailored, TailoredResume) or not tailored.items:
        return False

    threshold = get_settings().enrich_threshold
    return len(tailored.kept_or_reworded()) < threshold


def _should_run_approval_loop(
    result: dict[str, object],
    *,
    no_approve: bool,
) -> bool:
    """Decide whether to enter the #78 iterative approval loop.

    Triggers when:
      - the user didn't explicitly opt out via `--no-approve`
      - stdin is a TTY (we need to prompt the user)
      - the first tailor pass actually produced a tailored resume
        (the #44 skip gate may have bypassed optimization entirely)
    """
    import sys

    if no_approve or not sys.stdin.isatty():
        return False

    from lucky_resume.state import TailoredResume

    tailored = result.get("tailored_resume")
    return isinstance(tailored, TailoredResume) and bool(tailored.items)


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
    no_approve: bool = typer.Option(
        False,
        "--no-approve",
        help=(
            "Skip the iterative approval loop (#78) and render the first tailored "
            "version directly. Used for scripted / headless runs and CI."
        ),
    ),
    max_iter: int = typer.Option(
        None,
        "--max-iter",
        help=(
            "Maximum approval-loop iterations before the 'continue anyway?' prompt "
            "(default 3, also settable via RESUME_MAX_ITERATIONS env)."
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
    from lucky_resume.tools.output_dir import resolve_output_dir

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
        # `builtin:<name>` resolves to a bundled YAML; skip the filesystem
        # check for those (the resolver below verifies the name maps to a
        # known preset).
        style_str = str(style)
        if not is_builtin_identifier(style_str) and not style.exists():
            raise typer.BadParameter(f"--style path {style} does not exist.")
        initial["style_path"] = style_str

    tailor_graph = build_tailor_graph()
    finalize_graph = build_finalize_graph()
    prompter = RichPrompter(console)
    with Status("[bold cyan]Running optimization pipeline...", console=console):
        result = tailor_graph.invoke(initial)

    # --- Auto-enrich: if the first tailor pass is thin, offer an interview ---
    if _should_offer_enrich(result, no_enrich=no_enrich, master_path=master):
        if run_auto_enrich(
            prompter=prompter,
            master_path=master,
            facts_path=resolved_facts,
            jd_text=jd_text,
        ):
            # New items landed in facts_bank.yaml; re-invoke the tailor graph so
            # load_master → optimize_content picks them up.
            console.print("[cyan]Re-running optimization with enriched facts...[/cyan]")
            if resolved_facts is None:
                # `run_auto_enrich` created data/facts_bank.yaml if it wasn't there.
                resolved_facts = DEFAULT_FACTS_PATH
                initial["facts_path"] = str(resolved_facts)
            with Status("[bold cyan]Re-running pipeline...", console=console):
                result = tailor_graph.invoke(initial)

    # --- #78: iterative approval loop — user gates each tailored version and
    # grows facts_bank with LLM-proposed edits until the ATS score meets their
    # bar or the iteration cap fires. Headless runs (--no-approve / non-TTY)
    # skip the loop and render the first tailored version as-is.
    if _should_run_approval_loop(result, no_approve=no_approve):
        effective_max_iter = (
            max_iter if max_iter is not None else get_settings().resume_max_iterations
        )
        result = run_approval_loop(
            prompter=prompter,
            tailor_graph=tailor_graph,
            initial_result=result,
            initial_input=initial,
            max_iterations=effective_max_iter,
        )

    # Finalize: generate PDF + write results/diff/yaml once, from the final state.
    with Status("[bold cyan]Rendering PDF and writing outputs...", console=console):
        result = finalize_graph.invoke(result)

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

    # Display ATS report — composite + per-dimension breakdown (#81).
    ats: ATSScore = result.get("ats_score", ATSScore())
    if ats.score > 0:
        _display_ats_report(ats)

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
    from lucky_resume.nodes.parse_resume import parse_resume as parse_resume_node
    from lucky_resume.state import ResumeMaster, ResumeOptimizerState
    from lucky_resume.tools.bootstrap_interview import run_interview, should_run_interview
    from lucky_resume.tools.master_resume import save_master

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
        master = run_interview(master, prompter=RichPrompter(console))

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
        lucky-resume run --master M.yaml --job J.txt --style <output>
    """
    from lucky_resume.tools.style import save_style
    from lucky_resume.tools.style_from_docx import (
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
            f"  lucky-resume run --master ... --job ... --style {output}",
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
        _display_ats_report(ats)
    elif not errors:
        console.print("[yellow]No ATS score produced.[/yellow]")


def _display_ats_report(ats: ATSScore) -> None:
    """Render the #81 multi-dimensional ATS report as a Rich table alongside
    the composite score. Falls back to the pre-#81 shape gracefully for the
    back-compat alias — all new fields default to empty / False, so the table
    just shows zero rows in those sections.
    """
    from rich.table import Table

    color = _score_color(ats.score)
    console.print(f"\n[bold green]ATS Composite:[/bold green] [{color}]{ats.score:.0%}[/{color}]")
    console.print(f"  [dim]{ats.reasoning}[/dim]")

    # Structural dimensions
    structural_table = Table(title="Structural Checks", title_style="bold", show_header=True)
    structural_table.add_column("Dimension")
    structural_table.add_column("Status", justify="center")
    structural_table.add_column("Detail", style="dim")
    structural_table.add_row(
        "Contact info",
        _status_glyph(
            ats.contact.email_present and ats.contact.phone_present and ats.contact.address_present
        ),
        _contact_detail(ats.contact),
    )
    structural_table.add_row(
        "Sections",
        _status_glyph(
            ats.sections.summary
            and ats.sections.experience
            and ats.sections.education
            and ats.sections.skills
        ),
        _sections_detail(ats.sections),
    )
    structural_table.add_row(
        "Job title match",
        "✓" if ats.job_title.exact_match else ("~" if ats.job_title.partial_match else "✗"),
        _title_detail(ats.job_title),
    )
    structural_table.add_row(
        "Measurable results",
        _status_glyph(ats.measurable_results_count >= 5),
        f"{ats.measurable_results_count} quantified lines",
    )
    structural_table.add_row(
        "Word count",
        _status_glyph(ats.word_count_ok),
        f"{ats.word_count} words (target 400-1000)",
    )
    console.print(structural_table)

    # Hard skill table
    if ats.hard_skills:
        hard_table = Table(title="Hard Skills", title_style="bold", show_header=True)
        hard_table.add_column("Skill")
        hard_table.add_column("Resume", justify="right")
        hard_table.add_column("JD", justify="right")
        for row in ats.hard_skills:
            hard_table.add_row(row.name, str(row.resume_count), str(row.jd_count))
        console.print(hard_table)

    if ats.soft_skills:
        soft_table = Table(title="Soft Skills", title_style="bold", show_header=True)
        soft_table.add_column("Skill")
        soft_table.add_column("Resume", justify="right")
        soft_table.add_column("JD", justify="right")
        for row in ats.soft_skills:
            soft_table.add_row(row.name, str(row.resume_count), str(row.jd_count))
        console.print(soft_table)

    if ats.tone_flags:
        console.print("\n[bold yellow]Tone flags:[/bold yellow]")
        for flag in ats.tone_flags:
            console.print(f'  [yellow]•[/yellow] "{flag.phrase}" — {flag.suggestion}')


def _status_glyph(ok: bool) -> str:
    return "[green]✓[/green]" if ok else "[yellow]⚠[/yellow]"


def _contact_detail(contact: object) -> str:
    fields = [
        ("email", "email_present"),
        ("phone", "phone_present"),
        ("address", "address_present"),
    ]
    missing = [name for name, attr in fields if not getattr(contact, attr, False)]
    return "all present" if not missing else f"missing: {', '.join(missing)}"


def _sections_detail(sections: object) -> str:
    missing: list[str] = []
    for name in ("summary", "experience", "education", "skills"):
        if not getattr(sections, name, False):
            missing.append(name)
    return "all present" if not missing else f"missing: {', '.join(missing)}"


def _title_detail(job_title: object) -> str:
    jd = getattr(job_title, "jd_title", "") or ""
    if getattr(job_title, "exact_match", False):
        return f"'{jd}' exact match"
    if getattr(job_title, "partial_match", False):
        return f"'{jd}' partial match"
    return f"'{jd}' not found on resume" if jd else "no JD title detected"


if __name__ == "__main__":
    app()
