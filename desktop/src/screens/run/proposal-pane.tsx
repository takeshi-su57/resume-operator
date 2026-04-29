import { Check, Loader2, Pencil, X } from "lucide-react";

import { DiffView } from "@/components/diff-view";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { Proposal } from "@/lib/events";
import { useRunSession } from "@/state/run-session";

const KIND_LABELS: Record<string, string> = {
  rewrite_master: "Rewrite of an existing master bullet",
  rewrite_fact: "Polish of a facts-bank entry",
  new_fact: "NEW bullet — LLM extrapolation, verify truth",
  new_skill: "NEW skill — verify you actually have this",
};

type Props = {
  onAccept: () => void;
  onReject: () => void;
  onFix: () => void;
  onQuit: () => void;
  disabled?: boolean;
};

/**
 * Center pane during the approval loop: the current proposal with
 * grounding source, diff (original vs proposed), rationale, and the
 * three-button decision row. Keyboard handlers live one level up
 * (Workspace) so they can be conditional on the current phase.
 */
export function ProposalPane({
  onAccept,
  onReject,
  onFix,
  onQuit,
  disabled,
}: Props) {
  const proposal = useRunSession((s) => s.currentProposal);
  const index = useRunSession((s) => s.proposalIndex);
  const total = useRunSession((s) => s.proposalTotal);

  if (!proposal) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-fg-dim">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        LLM is proposing edits…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header proposal={proposal} index={index} total={total} />
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        <DiffSection proposal={proposal} />
        {proposal.rationale && (
          <section className="text-sm text-fg-muted">
            <h4 className="mb-1 text-xs uppercase tracking-wider text-fg-dim">
              Rationale
            </h4>
            <p className="leading-relaxed">{proposal.rationale}</p>
          </section>
        )}
      </div>
      <ActionBar
        onAccept={onAccept}
        onReject={onReject}
        onFix={onFix}
        onQuit={onQuit}
        disabled={disabled}
      />
      <ProgressBar index={index} total={total} />
    </div>
  );
}

function Header({
  proposal,
  index,
  total,
}: {
  proposal: Proposal;
  index: number;
  total: number;
}) {
  const label = KIND_LABELS[proposal.kind] ?? proposal.kind;
  return (
    <header className="border-b border-border px-6 py-3 flex items-baseline justify-between gap-4">
      <div className="min-w-0 flex-1">
        <p className="text-xs uppercase tracking-wider text-fg-muted">
          Proposal {index} / {total}
        </p>
        <h3 className="mt-0.5 text-sm font-bold text-fg truncate">{label}</h3>
      </div>
      <div className="flex items-center gap-2 text-xs text-fg-dim">
        <span className="rounded-sm border border-border bg-bg-raised px-1.5 py-0.5 font-mono">
          {proposal.kind}
        </span>
        <span className="rounded-sm border border-border bg-bg-raised px-1.5 py-0.5 font-mono">
          {proposal.grounding_source_id}
        </span>
      </div>
    </header>
  );
}

function DiffSection({ proposal }: { proposal: Proposal }) {
  if (!proposal.original_text) {
    // new_fact / new_skill — show the proposed text as-is, no diff.
    return (
      <section>
        <h4 className="mb-1 text-xs uppercase tracking-wider text-fg-dim">
          New
        </h4>
        <p className="font-mono text-sm leading-relaxed text-success">
          {proposal.proposed_text}
        </p>
      </section>
    );
  }
  return (
    <section>
      <h4 className="mb-1 text-xs uppercase tracking-wider text-fg-dim">
        Diff
      </h4>
      <DiffView
        original={proposal.original_text}
        proposed={proposal.proposed_text}
        className="rounded-md bg-bg-raised border border-border-subtle p-3"
      />
    </section>
  );
}

function ActionBar({
  onAccept,
  onReject,
  onFix,
  onQuit,
  disabled,
}: Props) {
  return (
    <div
      className="border-t border-border px-6 py-2 flex items-center gap-2"
      data-no-select
    >
      <Button
        variant="primary"
        onClick={onAccept}
        disabled={disabled}
        title="Accept (⏎)"
      >
        <Check className="h-4 w-4" />
        Accept
        <span className="kbd ml-1">⏎</span>
      </Button>
      <Button
        variant="secondary"
        onClick={onReject}
        disabled={disabled}
        title="Reject (x)"
      >
        <X className="h-4 w-4" />
        Reject
        <span className="kbd ml-1">x</span>
      </Button>
      <Button
        variant="secondary"
        onClick={onFix}
        disabled={disabled}
        title="Fix (f)"
      >
        <Pencil className="h-4 w-4" />
        Fix…
        <span className="kbd ml-1">f</span>
      </Button>
      <div className="ml-auto">
        <Button
          variant="ghost"
          onClick={onQuit}
          disabled={disabled}
          title="Quit approval (q)"
        >
          Quit
          <span className="kbd ml-1">q</span>
        </Button>
      </div>
    </div>
  );
}

function ProgressBar({ index, total }: { index: number; total: number }) {
  if (!total) return null;
  return (
    <div className="border-t border-border-subtle bg-bg-panel px-6 py-1.5 flex items-center gap-3">
      <div className="flex-1 h-1 rounded-full bg-bg-raised overflow-hidden">
        <div
          className={cn(
            "h-full bg-accent transition-all",
          )}
          style={{ width: `${(index / total) * 100}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-fg-dim">
        {index} / {total}
      </span>
    </div>
  );
}
