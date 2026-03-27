# Logging Rules

## Setup

Every module that logs must use the standard library pattern:

```python
import logging

logger = logging.getLogger(__name__)
```

Do NOT use `print()` for operational output — use `logger` or Rich console (CLI layer only).

## Log Levels

| Level | What to log | Example |
|-------|------------|---------|
| `DEBUG` | Full prompt text, raw LLM response, resume raw text, detailed state dumps | `logger.debug("LLM prompt: %s", prompt)` |
| `INFO` | Node entry/exit, key metrics, LLM call timing, pipeline progress | `logger.info("parse_resume: completed — skills=%d", len(skills))` |
| `WARNING` | Recoverable issues, fallback behavior, missing optional config | `logger.warning("No job description provided, skipping gap analysis")` |
| `ERROR` | Failures recorded in `state.errors`, exceptions caught in nodes | `logger.error("parse_resume: PDF extraction failed: %s", exc)` |

## Node Logging Pattern

Every node function must log at these points:

```python
def example_node(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("example_node: starting")

    # ... do work ...

    logger.info("example_node: completed — <key metrics>")
    return {<fields>}
```

On error:
```python
    except Exception as exc:
        logger.error("example_node: <description>: %s", exc)
        errors.append(f"example_node: <description>: {exc}")
```

Key metrics to log at INFO on completion:
- `parse_resume` — char count from PDF, field counts (skills, experience, education)
- `ats_score` — score value, keyword match/gap counts
- `analyze_gaps` — gap count, strength count, suggestion count
- `optimize_content` — number of sections, changes made count
- `generate_pdf` — output path, file size
- `report_results` — output path

## LLM Call Logging

In `tools/llm_provider.py` or at the call site in nodes:

```python
logger.info("LLM call: provider=%s, model=%s", provider, model)
logger.debug("LLM prompt: %s", prompt)
logger.info("LLM response received in %.1fs (%d chars)", elapsed, len(content))
logger.debug("LLM response: %s", content)
```

Never log prompt content or LLM response content at INFO level — use DEBUG only.

## CLI Log Configuration

`main.py` configures logging based on a `--verbose` / `-v` flag:

- Default (no flag): `WARNING` level — quiet output, only Rich console display
- `--verbose`: `DEBUG` level — full pipeline visibility

```python
logging.basicConfig(
    level=logging.DEBUG if verbose else logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
```

## Security Constraints (from security.md)

- Never log API keys, tokens, or passwords at any level
- Never log full resume text or personal data at INFO — DEBUG only
- Safe to log at INFO: file paths, score values, counts, timing, status messages

## Anti-Patterns (Do NOT)

- Use `print()` for debug output — use `logger.debug()`
- Log at INFO inside tight loops — use DEBUG
- Create custom logging handlers or formatters per module — use `basicConfig` in CLI
- Use f-strings in log calls — use `%s` formatting for lazy evaluation: `logger.info("x=%s", x)`
- Log sensitive data (API keys, resume PII) at INFO or above
- Skip the node entry/exit log — it's how we trace pipeline progress
