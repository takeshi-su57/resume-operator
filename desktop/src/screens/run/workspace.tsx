import { useEffect, useRef, useState } from "react";

import { useRunSession } from "@/state/run-session";

import { AtsSidePane } from "./ats-side-pane";
import { EnrichPolishedPane } from "./enrich-polished-pane";
import { EnrichQuestionPane } from "./enrich-question-pane";
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
 * wires keyboard shortcuts, and owns the Fix / Rejection modals plus
 * the deferred enrichment-edit reply (the `e` choose pick fires a
 * follow-up text prompt the user fills in via the polished pane).
 */
export function RunWorkspace({ controller, onReset }: Props) {
  const phase = useRunSession((s) => s.phase);
  const pending = useRunSession((s) => s.pendingPrompt);
  const promptRole = controller.promptRole;

  const [fixOpen, setFixOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);

  // When the user picks "Edit" on a polished bullet, we send `e` —
  // the server then fires a `text` prompt asking for the edited
  // wording. Stash the draft until that prompt arrives.
  const pendingEnrichEditRef = useRef<string | null>(null);

  // Open the fix modal whenever the controller transitions to
  // `fixing` (server sent the "What should change?" text prompt).
  useEffect(() => {
    if (phase === "fixing") setFixOpen(true);
    else setFixOpen(false);
  }, [phase]);

  // When the deferred enrich-edit text prompt arrives, send the
  // stashed draft.
  useEffect(() => {
    if (
      pending?.kind === "text" &&
      promptRole === "enrich_edit" &&
      pendingEnrichEditRef.current !== null
    ) {
      const draft = pendingEnrichEditRef.current;
      pendingEnrichEditRef.current = null;
      controller.sendText(draft);
    }
  }, [pending, promptRole, controller]);

  // --- Keyboard shortcuts -------------------------------------------------
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName;
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        rejectOpen ||
        fixOpen
      ) {
        return;
      }
      if (phase === "approval") {
        switch (e.key) {
          case "Enter":
            e.preventDefault();
            controller.acceptProposal();
            return;
          case "x":
          case "X":
            e.preventDefault();
            setRejectOpen(true);
            controller.beginRejectProposal();
            return;
          case "f":
          case "F":
            e.preventDefault();
            controller.beginFixProposal();
            return;
          case "q":
          case "Q":
            e.preventDefault();
            controller.quitApproval();
            return;
        }
      }
      if (phase === "enrich_polished") {
        switch (e.key) {
          case "a":
          case "A":
            e.preventDefault();
            controller.acceptEnrich();
            return;
          case "r":
          case "R":
            e.preventDefault();
            controller.rejectEnrich();
            return;
          case "s":
          case "S":
            e.preventDefault();
            controller.skipEnrich();
            return;
          case "q":
          case "Q":
            e.preventDefault();
            controller.quitEnrich();
            return;
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [phase, controller, fixOpen, rejectOpen]);

  return (
    <div className="grid h-full grid-cols-[200px_1fr_260px]">
      <NodeTimeline />
      <section className="flex h-full min-w-0 flex-col bg-bg-subtle">
        <CenterPane
          controller={controller}
          onReset={onReset}
          onEnrichEditSubmit={(text) => {
            // Send `e` to the server's choose prompt. The text prompt
            // that follows is answered by the effect above once it
            // arrives, using the stashed draft.
            pendingEnrichEditRef.current = text;
            controller.editEnrich();
          }}
        />
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
  onEnrichEditSubmit,
}: {
  controller: ReturnType<typeof useRunController>;
  onReset: () => void;
  onEnrichEditSubmit: (text: string) => void;
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

  if (phase === "enrich_question") {
    return (
      <EnrichQuestionPane
        onSubmit={(text) => controller.sendText(text)}
        onSkip={() => controller.sendText("skip")}
        onQuit={() => controller.sendText("quit")}
      />
    );
  }

  if (phase === "enrich_polished") {
    return (
      <EnrichPolishedPane
        onAccept={controller.acceptEnrich}
        onEdit={onEnrichEditSubmit}
        onReject={controller.rejectEnrich}
        onSkip={controller.skipEnrich}
        onQuit={controller.quitEnrich}
      />
    );
  }

  return <PlaceholderPane phase={phase} />;
}

function PlaceholderPane({ phase }: { phase: string }) {
  const messages: Record<string, string> = {
    starting: "Connecting to engine…",
    running: "Pipeline running. Watch the timeline on the left.",
    fixing: "Send your feedback in the modal — LLM will revise.",
  };
  return (
    <div className="flex h-full items-center justify-center text-sm text-fg-dim text-center px-6">
      <p>{messages[phase] ?? "…"}</p>
    </div>
  );
}
