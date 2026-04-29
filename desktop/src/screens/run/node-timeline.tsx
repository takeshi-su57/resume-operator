import { Check, Loader2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import { useRunSession, type NodeStep } from "@/state/run-session";

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

type NodeView = {
  status: NodeStatus;
  /** Wall-clock duration in seconds when known (started + ended), else
   * undefined (pending) or the live tick (running). */
  elapsedSeconds?: number;
};

/**
 * Left pane: live node timeline + iteration history.
 *
 * Renders the canonical graph node order regardless of which events
 * arrived. Each node's state derives from the latest `node_event`
 * matching its name. The currently-running node ticks an elapsed
 * counter at ~10 Hz so the user can see real progress, completed
 * nodes show their final duration, and a vertical chain connects
 * the steps for that classic wizard feel.
 */
export function NodeTimeline() {
  const events = useRunSession((s) => s.nodeEvents);
  const iterations = useRunSession((s) => s.iterationHistory);

  // Tick clock — only updates when a node is currently running. Keeps
  // the elapsed counter live without thrashing during idle phases.
  const tick = useLiveClock(events);

  const views = useMemo(() => {
    const v = new Map<string, NodeView>();
    const startedAt = new Map<string, number>();
    for (const e of events) {
      if (e.phase === "start") {
        startedAt.set(e.node, e.timestamp);
        v.set(e.node, { status: "running" });
      } else if (e.phase === "end") {
        const startTs = startedAt.get(e.node);
        v.set(e.node, {
          status: "done",
          elapsedSeconds:
            startTs !== undefined ? (e.timestamp - startTs) / 1000 : undefined,
        });
      } else if (e.phase === "error") {
        const startTs = startedAt.get(e.node);
        v.set(e.node, {
          status: "error",
          elapsedSeconds:
            startTs !== undefined ? (e.timestamp - startTs) / 1000 : undefined,
        });
      }
    }
    // Fill live elapsed for any still-running node.
    for (const [node, view] of v) {
      if (view.status === "running") {
        const startTs = startedAt.get(node);
        if (startTs !== undefined) {
          view.elapsedSeconds = Math.max(0, (tick - startTs) / 1000);
        }
      }
    }
    return v;
  }, [events, tick]);

  return (
    <aside
      className="flex h-full w-[200px] flex-col border-r border-border bg-bg-panel"
      data-no-select
    >
      <div className="border-b border-border px-3 py-2 text-xs uppercase tracking-wider text-fg-muted">
        Node timeline
      </div>
      <ol className="relative flex-1 overflow-y-auto py-2">
        {NODE_ORDER.map((node, idx) => (
          <Step
            key={node}
            label={NODE_LABELS[node] ?? node}
            view={views.get(node) ?? { status: "pending" }}
            isLast={idx === NODE_ORDER.length - 1}
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

function Step({
  label,
  view,
  isLast,
}: {
  label: string;
  view: NodeView;
  isLast: boolean;
}) {
  const { status, elapsedSeconds } = view;
  return (
    <li
      className={cn(
        "relative flex items-start gap-2 px-3 py-1.5 text-sm transition-colors duration-150",
        status === "running" && "bg-accent/10",
      )}
    >
      <div className="relative z-10 flex flex-col items-center">
        <StatusGlyph status={status} />
        {!isLast && (
          <span
            aria-hidden
            className={cn(
              "mt-0.5 h-4 w-px transition-colors duration-300",
              status === "done" || status === "error"
                ? "bg-border-strong"
                : "bg-border-subtle",
            )}
          />
        )}
      </div>
      <div className="min-w-0 flex-1 -mt-0.5">
        <span
          className={cn(
            "block leading-snug transition-colors duration-150",
            status === "pending" && "text-fg-faint",
            status === "running" && "text-fg font-bold",
            status === "done" && "text-fg-muted",
            status === "error" && "text-danger",
          )}
        >
          {label}
        </span>
        {elapsedSeconds !== undefined && (
          <span
            className={cn(
              "block text-[10px] tabular-nums leading-tight",
              status === "running" ? "text-accent" : "text-fg-faint",
            )}
          >
            {formatElapsed(elapsedSeconds)}
          </span>
        )}
      </div>
    </li>
  );
}

function StatusGlyph({ status }: { status: NodeStatus }) {
  if (status === "running") {
    return (
      <span
        className={cn(
          "relative inline-flex h-3.5 w-3.5 items-center justify-center",
        )}
      >
        <span className="absolute inset-0 rounded-full border border-accent/40 animate-ping" />
        <Loader2 className="h-3 w-3 text-accent animate-spin" />
      </span>
    );
  }
  if (status === "done") {
    return (
      <span
        className={cn(
          "inline-flex h-3.5 w-3.5 items-center justify-center rounded-full",
          "bg-success/15 text-success animate-step-complete",
        )}
      >
        <Check className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-danger/15 text-danger">
        <X className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    );
  }
  return (
    <span className="inline-block h-3.5 w-3.5 rounded-full border border-border-subtle bg-bg-panel" />
  );
}

function formatElapsed(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

/**
 * Returns the current epoch ms, refreshing at ~10 Hz only while at
 * least one node is running. A pure idle session stays at the last
 * tick — no wasted re-renders.
 */
function useLiveClock(events: NodeStep[]): number {
  const [now, setNow] = useState(() => Date.now());
  const hasRunning = useMemo(() => {
    const status = new Map<string, "running" | "done" | "error">();
    for (const e of events) {
      if (e.phase === "start") status.set(e.node, "running");
      else if (e.phase === "end") status.set(e.node, "done");
      else if (e.phase === "error") status.set(e.node, "error");
    }
    for (const v of status.values()) if (v === "running") return true;
    return false;
  }, [events]);

  useEffect(() => {
    if (!hasRunning) return;
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, [hasRunning]);

  return now;
}
