import { useCallback, useEffect, useRef } from "react";

import type { ServerMessage } from "@/lib/events";
import { useRunSession } from "@/state/run-session";
import { useTaskStore } from "@/state/task-store";

/**
 * Run controller — bridges a registered backend task into the
 * `useRunSession` store the legacy three-pane workspace already
 * understands.
 *
 * Two passes through the task's event log drive the state machine:
 *
 *   - **Wire-format events** (`node_event`, `confirm`, `choose`, etc.)
 *     are dispatched into `useRunSession` exactly like the legacy
 *     `useFlowSocket`-based controller did. The task's `events` array
 *     is the authoritative log; we replay any newly-appended slice on
 *     every store update.
 *
 *   - **Task-level state** (`status`, `result`, `error`) is mirrored
 *     into `useRunSession.phase` and `setResult` / `setError` so the
 *     existing workspace components (which key off `phase`) keep
 *     working without modification.
 *
 * The CLI-side wording on `confirm` messages remains the source of
 * truth for routing — exact same substring-matching as the legacy
 * controller. Phase 5 deliberately preserves that behavior so the
 * proposal / enrich / iteration panels don't all need to be rewritten
 * in the same PR.
 */

const ACCEPT_TAILORED = "Accept this tailored version";
const CONTINUE_ANYWAY = "Continue anyway";
const START_ENRICH = "Start an enrichment session";

type PromptRole =
  | "iteration_accept"
  | "iteration_continue"
  | "enrich_offer"
  | "approval_choice"
  | "approval_reason"
  | "approval_feedback"
  | "enrich_answer"
  | "enrich_choice"
  | "enrich_edit"
  | null;

export function useRunController(taskId: string | null) {
  const task = useTaskStore((s) => (taskId ? s.tasks[taskId] : null));
  const taskStore = useTaskStore();
  const session = useRunSession();

  const sessionRef = useRef(session);
  sessionRef.current = session;

  // How many events of `task.events` we've already pushed into the
  // session store. Replay slice = events[lastProcessed:].
  const lastProcessedRef = useRef(0);

  // Latest pending prompt's seq + role — needed to route replies back
  // to the right action bucket on the session store.
  const promptSeqRef = useRef<number | null>(null);
  const promptRoleRef = useRef<PromptRole>(null);

  // When we navigate into a different task, reset the bookkeeping so
  // we don't mistakenly skip events from the new task.
  useEffect(() => {
    sessionRef.current.reset();
    lastProcessedRef.current = 0;
    promptSeqRef.current = null;
    promptRoleRef.current = null;
  }, [taskId]);

  // Apply newly-appended events on every task update.
  useEffect(() => {
    if (!task) return;
    const s = sessionRef.current;
    const events = task.events;
    for (let i = lastProcessedRef.current; i < events.length; i++) {
      const ev = events[i] as unknown as ServerMessage;
      dispatchEvent(ev, s, promptSeqRef, promptRoleRef);
    }
    lastProcessedRef.current = events.length;

    // Mirror terminal task state into session phase.
    if (task.status === "completed" && task.result) {
      if (s.phase !== "done") s.setResult(task.result);
    } else if (task.status === "failed") {
      if (s.phase !== "error") s.setError(task.error || "Task failed");
    } else if (task.status === "cancelled") {
      if (s.phase !== "error") s.setError("Cancelled");
    } else if (task.status === "interrupted") {
      if (s.phase !== "error") {
        s.setError(
          task.error ||
            "Sidecar restarted before this task could finish.",
        );
      }
    } else if (task.status === "running" && s.phase === "idle") {
      s.setPhase("running");
    }

    // Clear pending prompt when the task says there isn't one.
    if (!task.pending_prompt) {
      if (s.pendingPrompt) s.setPending(null);
      promptSeqRef.current = null;
      promptRoleRef.current = null;
    }
  }, [task]);

  // --- public reply API ---------------------------------------------------

  const reply = useCallback(
    (value: string | boolean) => {
      if (!taskId) return;
      const seq = promptSeqRef.current;
      if (seq == null) return;
      taskStore.reply(taskId, seq, value);
      sessionRef.current.setPending(null);
      promptSeqRef.current = null;
      promptRoleRef.current = null;
    },
    [taskId, taskStore],
  );

  const acceptIteration = useCallback(() => reply(true), [reply]);
  const rejectIteration = useCallback(() => reply(false), [reply]);
  const continuePastCap = useCallback(() => reply(true), [reply]);
  const stopPastCap = useCallback(() => reply(false), [reply]);

  const acceptProposal = useCallback(() => {
    const proposal = sessionRef.current.currentProposal;
    if (proposal) sessionRef.current.recordApproved(proposal);
    reply("y");
  }, [reply]);

  const beginRejectProposal = useCallback(() => reply("n"), [reply]);

  const sendRejectionReason = useCallback(
    (reason: string) => {
      const proposal = sessionRef.current.currentProposal;
      if (proposal) sessionRef.current.recordRejected(proposal, reason);
      reply(reason);
    },
    [reply],
  );

  const beginFixProposal = useCallback(() => reply("f"), [reply]);
  const sendFixFeedback = useCallback(
    (feedback: string) => reply(feedback),
    [reply],
  );

  const quitApproval = useCallback(() => reply("q"), [reply]);

  const acceptEnrichOffer = useCallback(() => reply("y"), [reply]);
  const declineEnrichOffer = useCallback(() => reply("n"), [reply]);

  const acceptEnrich = useCallback(() => {
    const polished = sessionRef.current.currentPolished;
    if (polished) sessionRef.current.recordAcceptedEnrich(polished);
    reply("a");
  }, [reply]);
  const editEnrich = useCallback(() => reply("e"), [reply]);
  const rejectEnrich = useCallback(() => reply("r"), [reply]);
  const skipEnrich = useCallback(() => reply("s"), [reply]);
  const quitEnrich = useCallback(() => reply("q"), [reply]);

  const sendText = useCallback((text: string) => reply(text), [reply]);

  // Surface the attachment status so the UI can render
  // "connecting / closed / error" affordances.
  const attach = useTaskStore((s) =>
    taskId ? s.attachments[taskId] : undefined,
  );

  return {
    status: attach?.status ?? "idle",
    errorMsg: attach?.errorMessage ?? null,
    promptRole: promptRoleRef.current,

    // Iteration prompts
    acceptIteration,
    rejectIteration,
    continuePastCap,
    stopPastCap,

    // Approval-flow
    acceptProposal,
    beginRejectProposal,
    sendRejectionReason,
    beginFixProposal,
    sendFixFeedback,
    quitApproval,

    // Enrichment
    acceptEnrichOffer,
    declineEnrichOffer,
    acceptEnrich,
    editEnrich,
    rejectEnrich,
    skipEnrich,
    quitEnrich,

    sendText,
  } as const;
}

// ---------------------------------------------------------------------------
// Event dispatch — replays a single wire event into the run-session store
// ---------------------------------------------------------------------------

function dispatchEvent(
  msg: ServerMessage,
  s: ReturnType<typeof useRunSession.getState>,
  promptSeqRef: React.MutableRefObject<number | null>,
  promptRoleRef: React.MutableRefObject<PromptRole>,
) {
  switch (msg.type) {
    case "node_event":
      // Sub-step `progress` events also flow through here — the session
      // store doesn't distinguish them today, but the task-progress
      // widget reads them directly off `task.events` so no mapping is
      // needed at this layer.
      if (msg.phase === "start" || msg.phase === "end" || msg.phase === "error") {
        s.pushNodeEvent({
          node: msg.node,
          phase: msg.phase,
          timestamp: msg.timestamp,
          data: msg.data,
        });
      }
      return;
    case "status_start":
      s.pushStatusStart(msg.message, msg.at);
      return;
    case "status_end":
      s.pushStatusEnd(msg.at);
      return;
    case "render_iteration_header":
      s.pushIteration({
        iteration: msg.iteration,
        maxIter: msg.max_iter,
        score: msg.score,
        at: Date.now(),
      });
      return;
    case "render_proposal":
      s.setProposal(msg.proposal, msg.index, msg.total);
      return;
    case "render_question":
      s.setQuestion(msg.question, msg.index, msg.total);
      return;
    case "render_polished":
      s.setPolished(msg.polished);
      return;
    case "notice":
    case "panel":
      return;
    case "confirm": {
      promptSeqRef.current = msg.prompt_seq ?? null;
      if (msg.message.includes(ACCEPT_TAILORED)) {
        promptRoleRef.current = "iteration_accept";
        s.setPhase("iteration_confirm");
      } else if (msg.message.includes(CONTINUE_ANYWAY)) {
        promptRoleRef.current = "iteration_continue";
        s.setPhase("iteration_confirm");
      } else {
        promptRoleRef.current = "iteration_accept";
      }
      s.setPending({ ...msg, kind: "confirm" });
      return;
    }
    case "choose": {
      promptSeqRef.current = msg.prompt_seq ?? null;
      if (msg.choices.includes("y") && msg.choices.includes("n")) {
        if (msg.message.includes(START_ENRICH)) {
          promptRoleRef.current = "enrich_offer";
          s.setPhase("iteration_confirm");
        } else {
          promptRoleRef.current = "approval_choice";
        }
      } else if (msg.choices.includes("a") && msg.choices.includes("e")) {
        promptRoleRef.current = "enrich_choice";
      } else {
        promptRoleRef.current = "approval_choice";
      }
      s.setPending({ ...msg, kind: "choose" });
      return;
    }
    case "text": {
      promptSeqRef.current = msg.prompt_seq ?? null;
      if (msg.message.includes("Why not")) {
        promptRoleRef.current = "approval_reason";
      } else if (msg.message.includes("What should change")) {
        promptRoleRef.current = "approval_feedback";
        s.setPhase("fixing");
      } else if (msg.message.includes("Your wording")) {
        promptRoleRef.current = "enrich_edit";
      } else {
        promptRoleRef.current = "enrich_answer";
      }
      s.setPending({ ...msg, kind: "text" });
      return;
    }
    // task_status, snapshot — handled in the parent useEffect
    default:
      return;
  }
}
