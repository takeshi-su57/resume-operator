/**
 * Per-kind static topology for the task-progress widget.
 *
 * The backend emits real `node_event` start/end pairs for each
 * LangGraph node and `progress` sub-step events inside the heaviest
 * nodes (`ats_score`, `optimize_content`). The widget renders the
 * static node chain on the left and overlays sub-step state from the
 * live event log.
 *
 * Keep these arrays in sync with `src/lucky_resume/graph.py` —
 * specifically `build_score_graph()` and the run pipeline composed
 * from `build_tailor_graph()` + (optional enrich) + (optional
 * approval loop) + `build_finalize_graph()`.
 */

export type StepDescriptor = {
  /** Matches `NodeEvent.node` so we can map events → step. */
  id: string;
  /** Human-friendly label for the timeline. */
  label: string;
  /** Optional one-liner shown in muted text under the label. */
  hint?: string;
};

export type Topology = {
  steps: StepDescriptor[];
};

const SCORE_TOPOLOGY: Topology = {
  steps: [
    {
      id: "load_master",
      label: "Load resume",
      hint: "Read master YAML or PDF",
    },
    {
      id: "parse_resume",
      label: "Parse resume",
      hint: "Extract text (PDF only)",
    },
    {
      id: "ats_score",
      label: "Score against JD",
      hint: "Structural + keywords + tone",
    },
  ],
};

const RUN_TOPOLOGY: Topology = {
  steps: [
    { id: "load_master", label: "Load resume", hint: "Read master YAML / PDF" },
    { id: "parse_resume", label: "Parse resume", hint: "Extract text (PDF only)" },
    { id: "ats_score", label: "Initial ATS score", hint: "Structural + keywords + tone" },
    { id: "analyze_gaps", label: "Analyze gaps", hint: "Gaps, strengths, suggestions" },
    {
      id: "optimize_content",
      label: "Tailor content",
      hint: "Per-item rewrite under fabrication guard",
    },
    { id: "ats_score_tailored", label: "Score tailored", hint: "Re-score after tailoring" },
    { id: "generate_pdf", label: "Render PDF", hint: "ReportLab → resume.pdf" },
    { id: "report_results", label: "Write artifacts", hint: "Save tailored.yaml + diff.md" },
  ],
};

export function topologyFor(kind: "run" | "score"): Topology {
  return kind === "score" ? SCORE_TOPOLOGY : RUN_TOPOLOGY;
}
