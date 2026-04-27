import { useEffect, useState } from "react";

import { useRunSession } from "@/state/run-session";

import { AtsSidePane } from "./ats-side-pane";
import { FixModal } from "./fix-modal";
import { IterationConfirm } from "./iteration-confirm";
import { NodeTimeline } from "./node-timeline";
import { ProposalPane } from "./proposal-pane";
import { RejectionModal } from "./rejection-modal";
import { StatusPane } from "./status-pane";
import type { useRunController } from "./use-run-controller";

type Props = {
  controller: ReturnType<typeof useRunController>;
  onReset: () => void;
};

/**
 * Three-pane Run workspace orchestrator. Picks the right center-pane
 * component based on the session phase and the open prompt's role,
 * wires keyboard shortcuts, and owns the Fix / Rejection modals.
 *
 * Phase coverage in this commit:
 *   - `iteration_confirm` → IterationConfirm (Y/N gate)
 *   - `approval` → ProposalPane (3-button + Fix loop)
 *   - `done` / `error` → StatusPane
 *   - everything else → "running" placeholder driven by the timeline
 *
 * Phase 4 (#87) adds the enrichment center-pane components; this
 * file wires the slot for them today (`enrich_question` and
 * `enrich_polished` already render through StatusPane as a
 * placeholder until the Phase 4 components land).
 */
export function RunWorkspace({ controller, onReset }: Props) {
  const phase = useRunSession((s) => s.phase);
  const promptRole = controller.promptRole;

  const [fixOpen, setFixOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);

  // Open the fix modal whenever the controller transitions to
  // `fixing` (server sent the "What should change?" text prompt).
  useEffect(() => {
    if (phase === "fixing") setFixOpen(true);
    else setFixOpen(false);
  }, [phase]);

  // --- Keyboard shortcuts: Enter / x / f / q on the approval pane ---------
  useEffect(() => {
    if (phase !== "approval") return;
    const handler = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA" ||
        rejectOpen ||
        fixOpen
      ) {
        return;
      }
      switch (e.key) {
        case "Enter":
          e.preventDefault();
          controller.acceptProposal();
          break;
        case "x":
        case "X":
          e.preventDefault();
          setRejectOpen(true);
          // Tell the server we picked Reject; the modal collects the
          // (optional) reason and sends it with `sendRejectionReason`.
          controller.beginRejectProposal();
          break;
        case "f":
        case "F":
          e.preventDefault();
          controller.beginFixProposal();
          break;
        case "q":
        case "Q":
          e.preventDefault();
          controller.quitApproval();
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [phase, controller, fixOpen, rejectOpen]);

  return (
    <div className="grid h-full grid-cols-[200px_1fr_260px]">
      <NodeTimeline />
      <section className="flex h-full min-w-0 flex-col bg-bg-subtle">
        <CenterPane controller={controller} onReset={onReset} />
      </section>
      <AtsSidePane />

      <FixModal
        open={fixOpen && phase === "fixing"}
        onSubmit={(text) => {
          setFixOpen(false);
          controller.sendFixFeedback(text);
        }}
        onCancel={() => {
          setFixOpen(false);
          // Server is blocking on the "What should change?" prompt.
          // Empty submit is a no-op server-side (server keeps the
          // current proposal on screen and re-asks Y/N/F/Q).
          controller.sendFixFeedback("");
        }}
      />

      <RejectionModal
        open={rejectOpen && promptRole === "approval_reason"}
        onSubmit={(reason) => {
          setRejectOpen(false);
          controller.sendRejectionReason(reason);
        }}
        onCancel={() => {
          setRejectOpen(false);
          controller.sendRejectionReason("");
        }}
      />
    </div>
  );
}

function CenterPane({
  controller,
  onReset,
}: {
  controller: ReturnType<typeof useRunController>;
  onReset: () => void;
}) {
  const phase = useRunSession((s) => s.phase);
  const promptRole = controller.promptRole;

  if (phase === "done" || phase === "error") {
    return <StatusPane onReset={onReset} />;
  }

  if (phase === "approval") {
    return (
      <ProposalPane
        onAccept={controller.acceptProposal}
        onReject={() => controller.beginRejectProposal()}
        onFix={() => controller.beginFixProposal()}
        onQuit={controller.quitApproval}
      />
    );
  }

  if (phase === "iteration_confirm") {
    const onYes =
      promptRole === "iteration_continue"
        ? controller.continuePastCap
        : promptRole === "enrich_offer"
          ? controller.acceptEnrichOffer
          : controller.acceptIteration;
    const onNo =
      promptRole === "iteration_continue"
        ? controller.stopPastCap
        : promptRole === "enrich_offer"
          ? controller.declineEnrichOffer
          : controller.rejectIteration;
    return (
      <IterationConfirm
        promptRole={promptRole as "iteration_accept" | "iteration_continue" | "enrich_offer" | null}
        onYes={onYes}
        onNo={onNo}
      />
    );
  }

  // `starting`, `running`, `fixing`, `enrich_question`, `enrich_polished`
  // — show a quiet "watching the pipeline" placeholder. The node
  // timeline + status spinner on the side panes carry the visual
  // signal. Phase 4 (#87) replaces the enrich phases with their own
  // card stack here.
  return <PlaceholderPane phase={phase} />;
}

function PlaceholderPane({ phase }: { phase: string }) {
  const messages: Record<string, string> = {
    starting: "Connecting to engine…",
    running: "Pipeline running. Watch the timeline on the left.",
    fixing: "Send your feedback in the modal — LLM will revise.",
    enrich_question:
      "Enrichment interview — Phase 4 (#87) renders the question card here.",
    enrich_polished:
      "Enrichment polish — Phase 4 (#87) renders the accept/edit/reject card here.",
  };
  return (
    <div className="flex h-full items-center justify-center text-sm text-fg-dim text-center px-6">
      <p>{messages[phase] ?? "…"}</p>
    </div>
  );
}
