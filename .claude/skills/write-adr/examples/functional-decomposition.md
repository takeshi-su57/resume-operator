# Example: LangGraph Agent Framework ADR

File: `docs/adr/2026-03-25-langgraph-agent-framework.md`

```markdown
# LangGraph over Raw LangChain Agents

**Date:** 2026-03-25
**Status:** accepted

## Context

The resume optimizer agent needs to orchestrate a multi-step workflow: parse resume, score ATS compatibility, analyze gaps, optimize content, generate PDF, and report results. Future versions will add batch mode (multiple jobs) with conditional routing.

Options considered:
1. **Raw LangChain agents** — flexible but no built-in state management or graph structure
2. **LangGraph StateGraph** — typed state, explicit nodes/edges, checkpointing, conditional routing
3. **Custom orchestration** — hand-written pipeline with no framework

## Decision

We chose LangGraph StateGraph because:
- **Typed state**: `ResumeOptimizerState` as a Pydantic model provides type safety and validation
- **Explicit flow**: Nodes and edges make the pipeline visible and testable
- **Future routing**: Built-in `add_conditional_edges` for batch mode (loop over jobs)
- **Checkpointing**: Built-in persistence for resuming interrupted runs (future need)
- **Ecosystem**: LangChain integration for LLM provider abstraction

## Consequences

- **Easier:** Adding new nodes (e.g., cover letter generation) is straightforward — add a function, wire an edge
- **Easier:** Testing individual nodes in isolation — they're just functions that take state and return dicts
- **Easier:** Switching LLM providers — LangChain abstraction handled separately in tools layer
- **Harder:** Learning curve for LangGraph's state merging semantics
- **Harder:** ReportLab PDF generation is synchronous — need to handle within the graph node
```
