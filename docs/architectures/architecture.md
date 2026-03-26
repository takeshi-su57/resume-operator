# Architecture Overview

## System Diagram

```
                    ┌─────────────────────────────────────────┐
                    │           resume-operator CLI            │
                    │         (Typer + Rich console)           │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │        LangGraph StateGraph              │
                    │   (ResumeOptimizerState flows through)   │
                    └──────────────┬──────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   ┌─────────────┐      ┌──────────────┐        ┌────────────────┐
   │ tools/       │      │ nodes/        │        │ prompts/        │
   │ pdf_parser   │◄─────│ parse_resume  │───────►│ resume_parsing  │
   │ pdf_generator│◄─────│ ats_score     │───────►│ ats_scoring     │
   │ llm_provider │◄─────│ analyze_gaps  │───────►│ gap_analysis    │
   │              │◄─────│ optimize_cont │───────►│ content_optim   │
   │              │◄─────│ generate_pdf  │        │                 │
   │              │◄─────│ report_results│        │                 │
   └─────────────┘      └──────────────┘        └────────────────┘
```

## Agent Flow

```
START → parse_resume → ats_score → analyze_gaps → optimize_content → generate_pdf → report_results → END
```

### Node Descriptions

| Node | Purpose | Tools Used |
|------|---------|------------|
| `parse_resume` | Extract structured data from resume PDF | pdf_parser, llm_provider |
| `ats_score` | Score ATS compatibility vs job description | llm_provider |
| `analyze_gaps` | Identify gaps, strengths, suggestions | llm_provider |
| `optimize_content` | Rewrite resume content for better match | llm_provider |
| `generate_pdf` | Render optimized resume as PDF | pdf_generator |
| `report_results` | Save results to JSON | (file I/O) |

## Data Flow

1. **Input**: User provides `resume.pdf` + `job_description.txt`
2. **parse_resume**: PDF → raw text → LLM → `ResumeData` (structured)
3. **ats_score**: ResumeData + JobDescription → LLM → `ATSScore` (score, matches, gaps)
4. **analyze_gaps**: All above → LLM → `GapAnalysis` (gaps, strengths, suggestions)
5. **optimize_content**: All above → LLM → `OptimizedResume` (rewritten sections, change log)
6. **generate_pdf**: OptimizedResume → ReportLab → `output.pdf`
7. **report_results**: Full state → `data/results.json`

## Current Limitations

- Linear pipeline only — no conditional routing
- Single job description per run (batch mode planned)
- No LangGraph checkpointing (crash recovery not supported yet)
- PDF templates not customizable yet
- No CI/CD pipeline
