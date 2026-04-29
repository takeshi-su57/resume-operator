import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useMemo } from "react";

import { cn } from "@/lib/cn";
import type { TaskSnapshot } from "@/lib/events";
import { topologyFor, type StepDescriptor } from "@/lib/task-topology";

type Props = {
  task: TaskSnapshot;
  /** Hide the cumulative progress bar (e.g. when embedded in a denser layout). */
  compact?: boolean;
};

type StepState = "pending" | "active" | "done" | "error";

type RenderedStep = StepDescriptor & {
  state: StepState;
  /** Sub-step labels emitted via `phase: "progress"` events for this step. */
  subSteps: SubStepEntry[];
  startedAt: number | null;
  endedAt: number | null;
};

type SubStepEntry = {
  step: string;
  label: string;
  timestamp: number;
};

/**
 * Unified progress widget — renders the static topology of a task's
 * graph nodes on the left, with real-time start/end markers and
 * sub-step rows backed by the wire-format `phase: "progress"` events.
 *
 * Replaces the heuristic `score-progress.tsx` (time-thresholded fake
 * step advancement) with a real event-driven view that works for both
 * Run and Score tasks.
 */
export function TaskProgress({ task, compact }: Props) {
  const topology = topologyFor(task.kind);
  const rendered = useMemo(() => buildSteps(task, topology.steps), [task, topology.steps]);
  const completedCount = rendered.filter((s) => s.state === "done").length;
  const errored = rendered.some((s) => s.state === "error");
  const overallPct = Math.min(100, Math.round((completedCount / rendered.length) * 100));

  return (
    <div className="space-y-4">
      {!compact && (
        <OverallBar
          pct={overallPct}
          label={overallLabel(task, rendered)}
          tone={errored ? "error" : task.status === "completed" ? "done" : "active"}
        />
      )}
      <ol className="space-y-1">
        {rendered.map((step, idx) => (
          <Step
            key={step.id}
            step={step}
            isLast={idx === rendered.length - 1}
          />
        ))}
      </ol>
    </div>
  );
}

function Step({ step, isLast }: { step: RenderedStep; isLast: boolean }) {
  return (
    <li className="relative flex gap-3">
      <div className="flex flex-col items-center">
        <Glyph state={step.state} />
        {!isLast && (
          <div
            className={cn(
              "mt-1 w-px flex-1 bg-border",
              step.state === "done" && "bg-success/40",
            )}
          />
        )}
      </div>
      <div className="min-w-0 flex-1 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-xs font-medium",
              step.state === "pending" && "text-fg-faint",
              step.state === "active" && "text-fg",
              step.state === "done" && "text-fg-dim",
              step.state === "error" && "text-danger",
            )}
          >
            {step.label}
          </span>
          {step.state === "active" && step.startedAt != null && (
            <Elapsed startedAt={step.startedAt} />
          )}
          {step.state === "done" && step.startedAt != null && step.endedAt != null && (
            <span className="font-mono text-[0.6875rem] tabular-nums text-fg-faint">
              {formatDuration(step.endedAt - step.startedAt)}
            </span>
          )}
        </div>
        {step.hint && step.state !== "done" && (
          <p className="mt-0.5 text-[0.6875rem] text-fg-faint">{step.hint}</p>
        )}
        {step.subSteps.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {step.subSteps.map((sub, i) => {
              const isCurrent = step.state === "active" && i === step.subSteps.length - 1;
              return (
                <li
                  key={`${sub.step}-${sub.timestamp}-${i}`}
                  className={cn(
                    "flex items-center gap-1.5 text-[0.6875rem]",
                    isCurrent ? "text-accent" : "text-fg-faint",
                  )}
                >
                  <span
                    className={cn(
                      "inline-block h-1 w-1 rounded-full",
                      isCurrent ? "bg-accent animate-pulse" : "bg-fg-faint/60",
                    )}
                  />
                  <span>{sub.label}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </li>
  );
}

function Glyph({ state }: { state: StepState }) {
  if (state === "done") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-success/20 text-success">
        <CheckCircle2 className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (state === "error") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-danger/20 text-danger">
        <XCircle className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (state === "active") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/20 text-accent">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </span>
    );
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border" />
  );
}

function Elapsed({ startedAt }: { startedAt: number }) {
  const seconds = (Date.now() / 1000 - startedAt);
  return (
    <span className="font-mono text-[0.6875rem] tabular-nums text-fg-faint">
      {formatDuration(seconds)}
    </span>
  );
}

function OverallBar({
  pct,
  label,
  tone,
}: {
  pct: number;
  label: string;
  tone: "active" | "done" | "error";
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[0.6875rem]">
        <span className="text-fg-dim">{label}</span>
        <span className="font-mono tabular-nums text-fg-faint">{pct}%</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-bg-raised">
        <div
          className={cn(
            "h-full transition-all duration-300",
            tone === "done" && "bg-success",
            tone === "error" && "bg-danger",
            tone === "active" && "bg-accent",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Build the rendered step list from the task's event log.
// ---------------------------------------------------------------------------

type WireEvent =
  | {
      type: "node_event";
      node: string;
      phase: "start" | "end" | "error" | "progress";
      data: Record<string, unknown>;
      timestamp: number;
    }
  | { type: string; [k: string]: unknown };

function buildSteps(task: TaskSnapshot, topology: StepDescriptor[]): RenderedStep[] {
  const startMap: Record<string, number> = {};
  const endMap: Record<string, number> = {};
  const errorSet = new Set<string>();
  const subStepMap: Record<string, SubStepEntry[]> = {};
  let lastActiveNode: string | null = null;

  for (const raw of task.events) {
    const ev = raw as unknown as WireEvent;
    if (ev.type !== "node_event") continue;
    const phase = (ev as { phase?: string }).phase;
    const node = (ev as { node?: string }).node;
    const ts = (ev as { timestamp?: number }).timestamp ?? 0;
    const data = (ev as { data?: Record<string, unknown> }).data ?? {};
    if (!node) continue;
    if (phase === "start") {
      startMap[node] = ts;
      lastActiveNode = node;
    } else if (phase === "end") {
      endMap[node] = ts;
      if (lastActiveNode === node) lastActiveNode = null;
    } else if (phase === "error") {
      errorSet.add(node);
      endMap[node] = ts;
    } else if (phase === "progress") {
      const step = (data as { step?: string }).step ?? "";
      const label =
        (data as { label?: string }).label ?? humanizeStep(step);
      if (!subStepMap[node]) subStepMap[node] = [];
      subStepMap[node].push({ step, label, timestamp: ts });
    }
  }

  return topology.map((desc) => {
    const startedAt = startMap[desc.id] ?? null;
    const endedAt = endMap[desc.id] ?? null;
    let state: StepState;
    if (errorSet.has(desc.id)) state = "error";
    else if (endedAt != null) state = "done";
    else if (startedAt != null) state = "active";
    else state = "pending";
    return {
      ...desc,
      state,
      subSteps: subStepMap[desc.id] ?? [],
      startedAt,
      endedAt,
    };
  });
}

function overallLabel(task: TaskSnapshot, steps: RenderedStep[]): string {
  if (task.status === "completed") return "Complete";
  if (task.status === "failed") return task.error || "Failed";
  if (task.status === "cancelled") return "Cancelled";
  if (task.status === "interrupted") return "Interrupted";
  if (task.status === "awaiting_input") return "Awaiting your input";
  const active = steps.find((s) => s.state === "active");
  if (active) {
    const last = active.subSteps[active.subSteps.length - 1];
    return last ? last.label : active.label;
  }
  if (task.status === "queued") return "Queued";
  return "Running";
}

function humanizeStep(id: string): string {
  return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m${s.toString().padStart(2, "0")}s`;
}
