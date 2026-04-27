import { Check, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { useRunSession } from "@/state/run-session";

type Props = {
  promptRole:
    | "iteration_accept"
    | "iteration_continue"
    | "enrich_offer"
    | null
    | undefined;
  onYes: () => void;
  onNo: () => void;
  disabled?: boolean;
};

/**
 * Center pane during iteration / enrichment-offer Y/N gates. The
 * server's prompter can ask three different yes/no questions in the
 * run flow:
 *
 *   - "Accept this tailored version?" (per iteration)
 *   - "Continue anyway?" (after the iteration cap fires)
 *   - "Start an enrichment session?" (when tailor is thin)
 *
 * The wording differs but the UI shape is the same — show the open
 * question, the current ATS context, and a Yes/No pair.
 */
export function IterationConfirm({ promptRole, onYes, onNo, disabled }: Props) {
  const score = useRunSession((s) => s.currentScore);
  const iter = useRunSession((s) => s.currentIteration);
  const maxIter = useRunSession((s) => s.currentMaxIter);
  const pending = useRunSession((s) => s.pendingPrompt);

  const title =
    promptRole === "iteration_accept"
      ? "Accept this tailored version?"
      : promptRole === "iteration_continue"
        ? "Iteration cap reached — continue?"
        : promptRole === "enrich_offer"
          ? "Enrichment available"
          : "Continue?";

  const yesLabel =
    promptRole === "enrich_offer" ? "Start interview" : "Yes — accept";
  const noLabel =
    promptRole === "enrich_offer" ? "Skip" : "No — continue iterating";

  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="w-full max-w-xl panel p-6 space-y-4">
        <div>
          <h2 className="text-sm font-bold text-fg">{title}</h2>
          {pending?.kind && (
            <p className="mt-2 text-xs text-fg-dim leading-relaxed">
              {pending.message.replace(/\[\/?[^\]]+\]/g, "")}
            </p>
          )}
        </div>

        {score !== null && iter !== null && maxIter !== null && (
          <div className="grid grid-cols-2 gap-3">
            <Stat label="ATS score" value={`${Math.round(score * 100)}%`} score={score} />
            <Stat
              label="Iteration"
              value={`${iter} / ${maxIter}`}
            />
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <Button
            variant="primary"
            size="lg"
            onClick={onYes}
            disabled={disabled}
            className="flex-1"
          >
            <Check className="h-4 w-4" />
            {yesLabel}
          </Button>
          <Button
            variant="secondary"
            size="lg"
            onClick={onNo}
            disabled={disabled}
            className="flex-1"
          >
            <X className="h-4 w-4" />
            {noLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  score,
}: {
  label: string;
  value: string;
  score?: number;
}) {
  return (
    <div className="rounded-md border border-border-subtle bg-bg-subtle p-3">
      <p className="text-xs uppercase tracking-wider text-fg-muted">{label}</p>
      <p
        className={cn(
          "mt-1 text-xl font-bold tabular-nums",
          score === undefined
            ? "text-fg"
            : score >= 0.7
              ? "text-success"
              : score >= 0.4
                ? "text-warning"
                : "text-danger",
        )}
      >
        {value}
      </p>
    </div>
  );
}
