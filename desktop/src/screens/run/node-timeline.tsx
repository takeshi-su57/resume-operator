import { Check, Circle, CircleDot, X } from "lucide-react";
import { useMemo } from "react";

import { cn } from "@/lib/cn";
import { useRunSession } from "@/state/run-session";

const NODE_LABELS: Record<string, string> = {
  load_master: "load_master",
  parse_resume: "parse_resume",
  ats_score: "ats_score",
  analyze_gaps: "analyze",
  optimize_content: "optimize",
  ats_score_tailored: "ats_tailor",
  generate_pdf: "generate_pdf",
  report_results: "report",
};

// Order shown when no events have arrived yet — mirrors the tailor +
// finalize graph sequences.
const NODE_ORDER = [
  "load_master",
  "parse_resume",
  "ats_score",
  "analyze_gaps",
  "optimize_content",
  "ats_score_tailored",
  "generate_pdf",
  "report_results",
];

type NodeStatus = "pending" | "running" | "done" | "error";

/**
 * Left pane: live node timeline + iteration history.
 *
 * Renders the canonical graph node order regardless of which events
 * arrived. Each node's state derives from the latest `node_event`
 * matching its name. Below the timeline, a compact iteration log
 * shows ATS scores climbing (or regressing) per loop.
 */
export function NodeTimeline() {
  const events = useRunSession((s) => s.nodeEvents);
  const iterations = useRunSession((s) => s.iterationHistory);

  const status = useMemo(() => {
    const map = new Map<string, NodeStatus>();
    for (const e of events) {
      if (e.phase === "start") map.set(e.node, "running");
      else if (e.phase === "end") map.set(e.node, "done");
      else if (e.phase === "error") map.set(e.node, "error");
    }
    return map;
  }, [events]);

  return (
    <aside className="flex h-full w-[200px] flex-col border-r border-border bg-bg-panel" data-no-select>
      <div className="border-b border-border px-3 py-2 text-xs uppercase tracking-wider text-fg-muted">
        Node timeline
      </div>
      <ol className="flex-1 overflow-y-auto py-2">
        {NODE_ORDER.map((node) => (
          <Step
            key={node}
            label={NODE_LABELS[node] ?? node}
            status={status.get(node) ?? "pending"}
          />
        ))}
      </ol>

      {iterations.length > 0 && (
        <>
          <div className="border-t border-border-subtle border-b border-border px-3 py-2 text-xs uppercase tracking-wider text-fg-muted">
            Iterations
          </div>
          <ol className="px-3 py-2 text-xs space-y-1 max-h-40 overflow-y-auto">
            {iterations.map((it, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 text-fg-muted"
              >
                <span>
                  iter {it.iteration}/{it.maxIter}
                </span>
                <span
                  className={cn(
                    "tabular-nums font-bold",
                    it.score >= 0.7
                      ? "text-success"
                      : it.score >= 0.4
                        ? "text-warning"
                        : "text-danger",
                  )}
                >
                  {Math.round(it.score * 100)}%
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </aside>
  );
}

function Step({ label, status }: { label: string; status: NodeStatus }) {
  return (
    <li
      className={cn(
        "flex items-center gap-2 px-3 py-1 text-sm",
        status === "running" && "bg-accent/10",
      )}
    >
      <StatusGlyph status={status} />
      <span
        className={cn(
          status === "pending" && "text-fg-faint",
          status === "running" && "text-fg",
          status === "done" && "text-fg-muted",
          status === "error" && "text-danger",
        )}
      >
        {label}
      </span>
    </li>
  );
}

function StatusGlyph({ status }: { status: NodeStatus }) {
  if (status === "running")
    return <CircleDot className="h-3.5 w-3.5 text-accent animate-pulse" />;
  if (status === "done") return <Check className="h-3.5 w-3.5 text-success" />;
  if (status === "error") return <X className="h-3.5 w-3.5 text-danger" />;
  return <Circle className="h-3.5 w-3.5 text-fg-faint" />;
}
