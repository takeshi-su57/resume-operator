import { Check, Loader2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/cn";

type Props = {
  /** Becomes false the moment `useScore.mutate` resolves. We snap any
   * still-pending steps to "done" at that point. */
  isPending: boolean;
};

/**
 * One step in the heuristic ATS-analysis story. `cumMs` is the elapsed
 * milliseconds at which this step is considered "complete" if the
 * request is still in flight — a rough estimate calibrated against
 * what the score graph tends to do (two LLM calls + structural checks
 * + final composite). The animation is purely client-side; the server
 * still does its work in a single POST.
 */
type ScoreStep = {
  label: string;
  hint: string;
  cumMs: number;
};

const STEPS: ScoreStep[] = [
  { label: "Loading resume + JD", hint: "Reading files into memory", cumMs: 800 },
  {
    label: "Structural checks",
    hint: "Contact info, sections, word count, job title match",
    cumMs: 2_500,
  },
  {
    label: "Extracting JD keywords",
    hint: "Pulling hard + soft skills from the description",
    cumMs: 14_000,
  },
  {
    label: "Cross-checking your resume",
    hint: "Matching extracted skills against your experience",
    cumMs: 26_000,
  },
  {
    label: "Tone & cliche analysis",
    hint: "Flagging vague-positive phrasing the ATS de-prioritises",
    cumMs: 38_000,
  },
  {
    label: "Composing report",
    hint: "Weighting six dimensions into the composite score",
    cumMs: 42_000,
  },
];

/**
 * Score progression — visual story while `POST /api/score` is in
 * flight. Heuristic, not real-time: each step has a cumulative
 * threshold based on observed timing of the score graph; the active
 * step is the first whose threshold hasn't elapsed yet. When the
 * request resolves, `isPending` flips false and every step snaps to
 * done.
 *
 * The decoupling means we get a believable progression that ships
 * today; if the heuristic drifts from reality we can upgrade
 * `/api/score` to WebSocket and emit real `step_start` events later.
 */
export function ScoreProgress({ isPending }: Props) {
  const startedAt = useMemo(() => Date.now(), []);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isPending) return;
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, [isPending]);

  const elapsed = now - startedAt;
  const totalMs = STEPS[STEPS.length - 1].cumMs;
  const progress = isPending
    ? Math.min(0.97, elapsed / totalMs)
    : 1;
  // Index of the currently-running step (first one not yet done). When
  // `isPending` is false, we're past the end — every row renders done.
  const activeIdx = isPending
    ? STEPS.findIndex((s) => elapsed < s.cumMs)
    : STEPS.length;
  const safeActiveIdx = activeIdx === -1 ? STEPS.length - 1 : activeIdx;

  return (
    <div className="mx-auto flex h-full w-full max-w-md flex-col justify-center gap-5 px-6">
      <header className="space-y-2 text-center">
        <div className="inline-flex items-center gap-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-1.5 text-xs text-accent">
          <Sparkles className="h-3.5 w-3.5" />
          Running ATS analysis
        </div>
        <p className="text-xs text-fg-dim leading-relaxed">
          Two LLM calls + structural checks. Typical run: 30-60 seconds.
        </p>
      </header>

      <ProgressBar progress={progress} pulsing={isPending} />

      <ol className="space-y-1">
        {STEPS.map((step, idx) => {
          const status: "done" | "running" | "pending" =
            idx < safeActiveIdx ? "done" : idx === safeActiveIdx ? "running" : "pending";
          return <Step key={step.label} step={step} status={status} />;
        })}
      </ol>
    </div>
  );
}

function ProgressBar({
  progress,
  pulsing,
}: {
  progress: number;
  pulsing: boolean;
}) {
  return (
    <div className="relative h-1.5 overflow-hidden rounded-full bg-bg-raised">
      <div
        className={cn(
          "absolute inset-y-0 left-0 rounded-full transition-[width] duration-200 ease-out",
          pulsing
            ? "bg-gradient-to-r from-accent/70 via-accent to-accent/70 bg-[length:200%_100%] animate-shimmer"
            : "bg-success",
        )}
        style={{ width: `${Math.round(progress * 100)}%` }}
      />
    </div>
  );
}

function Step({
  step,
  status,
}: {
  step: ScoreStep;
  status: "pending" | "running" | "done";
}) {
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-md px-3 py-2 transition-colors duration-200",
        status === "running" && "bg-accent/10",
      )}
    >
      <Glyph status={status} />
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "text-sm leading-snug transition-colors duration-200",
            status === "pending" && "text-fg-faint",
            status === "running" && "text-fg font-bold",
            status === "done" && "text-fg-muted",
          )}
        >
          {step.label}
        </p>
        <p
          className={cn(
            "text-xs leading-tight",
            status === "running" ? "text-fg-dim" : "text-fg-faint",
          )}
        >
          {step.hint}
        </p>
      </div>
    </li>
  );
}

function Glyph({ status }: { status: "pending" | "running" | "done" }) {
  if (status === "running") {
    return (
      <span className="relative inline-flex h-5 w-5 items-center justify-center">
        <span className="absolute inset-0 rounded-full border border-accent/40 animate-ping" />
        <Loader2 className="h-4 w-4 text-accent animate-spin" />
      </span>
    );
  }
  if (status === "done") {
    return (
      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-success/15 text-success animate-step-complete">
        <Check className="h-3 w-3" strokeWidth={3} />
      </span>
    );
  }
  return (
    <span className="inline-block h-5 w-5 rounded-full border border-border-subtle bg-bg-panel" />
  );
}
