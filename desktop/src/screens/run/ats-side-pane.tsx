import { Loader2 } from "lucide-react";

import { cn } from "@/lib/cn";
import { useRunSession } from "@/state/run-session";

/**
 * Right pane — compact ATS context for the current iteration. Pulls
 * the latest score from the iteration history, the open status
 * spinner (if any), and a running session log (approved / rejected
 * counts). Phase 4 will swap this for the real ATSReport when the
 * server starts emitting `state_delta` events on `ats_score_tailored`
 * end. For Phase 3 we keep it lightweight — the headline numbers and
 * activity feed.
 */
export function AtsSidePane() {
  const score = useRunSession((s) => s.currentScore);
  const iter = useRunSession((s) => s.currentIteration);
  const maxIter = useRunSession((s) => s.currentMaxIter);
  const status = useRunSession((s) => s.statusStack);
  const approved = useRunSession((s) => s.approvedProposals.length);
  const rejected = useRunSession((s) => s.rejectedProposals.length);
  const accepted = useRunSession((s) => s.acceptedEnrichItems.length);

  const openStatus = status.find((s) => s.endedAt === null);

  return (
    <aside
      className="flex h-full w-[260px] flex-col border-l border-border bg-bg-panel"
      data-no-select
    >
      <div className="border-b border-border px-3 py-2 text-xs uppercase tracking-wider text-fg-muted">
        Session
      </div>

      <div className="px-4 py-4 space-y-4">
        <Block label="ATS score">
          {score === null ? (
            <p className="text-fg-faint text-sm">—</p>
          ) : (
            <p
              className={cn(
                "text-2xl font-bold tabular-nums",
                score >= 0.7
                  ? "text-success"
                  : score >= 0.4
                    ? "text-warning"
                    : "text-danger",
              )}
            >
              {Math.round(score * 100)}%
            </p>
          )}
        </Block>

        {iter !== null && maxIter !== null && (
          <Block label="Iteration">
            <p className="text-sm text-fg tabular-nums">
              {iter} / {maxIter}
            </p>
          </Block>
        )}

        <Block label="Decisions">
          <ul className="text-xs space-y-1">
            <li className="flex justify-between">
              <span className="text-fg-muted">Approved</span>
              <span className="tabular-nums text-success">{approved}</span>
            </li>
            <li className="flex justify-between">
              <span className="text-fg-muted">Rejected</span>
              <span className="tabular-nums text-danger">{rejected}</span>
            </li>
            <li className="flex justify-between">
              <span className="text-fg-muted">Enrich accepts</span>
              <span className="tabular-nums text-fg">{accepted}</span>
            </li>
          </ul>
        </Block>
      </div>

      {openStatus && (
        <div className="mt-auto border-t border-border-subtle bg-bg-raised px-3 py-2 text-xs text-fg-muted flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
          <span className="truncate">
            {openStatus.message.replace(/\[\/?[^\]]+\]/g, "")}
          </span>
        </div>
      )}
    </aside>
  );
}

function Block({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-fg-muted">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}
