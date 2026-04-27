import { useCallback, useEffect, useRef } from "react";

import type { ServerMessage } from "@/lib/events";
import { useFlowSocket } from "@/lib/ws";
import { useRunSession } from "@/state/run-session";

/**
 * The brains of the run screen — wires `/api/ws/run` to the
 * `useRunSession` zustand store and exposes one method per user
 * decision (`acceptVersion`, `rejectVersion`, `acceptProposal`, etc.).
 *
 * Two passes through the WebSocket protocol drive the state machine:
 *
 *   - **Outbound from the server** are dispatched in `handleMessage`,
 *     mutating the session store. Pending prompts (`confirm` / `choose`
 *     / `text`) are captured into `pendingPrompt` so the UI knows what
 *     panel to show and what reply shape to send back.
 *
 *   - **User actions** call methods on this controller, which inspect
 *     the open prompt's `type` and the in-flight server context (was
 *     this confirm asking about an iteration accept? About continuing
 *     past the cap?) and reply with the right value.
 *
 * The CLI-side wording on `confirm` messages is the source of truth
 * for routing — Phase 1's flows preserve the exact prompt strings, so
 * we match against substrings ("Accept this tailored version", "Start
 * an enrichment session") to disambiguate. If wording changes
 * upstream, the controller routes wrong; the alternative — adding a
 * `kind` field to every prompter call — is a Phase 1+ refactor we
 * deliberately deferred.
 */

type StartParams = {
  master?: string;
  resume?: string;
  facts?: string;
  job: string;
  output?: string;
  style?: string;
  no_enrich: boolean;
  no_approve: boolean;
  max_iter?: number;
};

const ACCEPT_TAILORED = "Accept this tailored version";
const CONTINUE_ANYWAY = "Continue anyway";
const START_ENRICH = "Start an enrichment session";

export function useRunController() {
  const session = useRunSession();
  const sessionRef = useRef(session);
  sessionRef.current = session;

  // Last open prompt's role — needed to route the reply into the
  // right action bucket (recordApproved / recordRejected / etc.).
  // Tracked separately from `pendingPrompt` so the user's reply
  // handler knows whether they were answering, e.g. a Y/N about
  // accepting the tailored version vs. accepting a single proposal.
  const promptRoleRef = useRef<
    | "iteration_accept"
    | "iteration_continue"
    | "enrich_offer"
    | "approval_choice"
    | "approval_reason"
    | "approval_feedback"
    | "enrich_answer"
    | "enrich_choice"
    | "enrich_edit"
    | null
  >(null);

  const handleMessage = useCallback((msg: ServerMessage) => {
    const s = sessionRef.current;
    switch (msg.type) {
      case "node_event":
        s.pushNodeEvent({
          node: msg.node,
          phase: msg.phase,
          timestamp: msg.timestamp,
          data: msg.data,
        });
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
        // Panels and notices land in the activity feed but don't gate
        // the UI. Phase 4 may surface enrichment intro panels in
        // their own slot — for now they're just informational.
        return;
      case "confirm":
        // Discriminate by message text — see comment at top of file.
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
      case "choose":
        if (msg.choices.includes("y") && msg.choices.includes("n")) {
          if (msg.message.includes(START_ENRICH)) {
            promptRoleRef.current = "enrich_offer";
            s.setPhase("iteration_confirm");
          } else {
            // Phase-1 / approval-flow choose calls (Y/N/F/Q).
            promptRoleRef.current = "approval_choice";
          }
        } else if (msg.choices.includes("a") && msg.choices.includes("e")) {
          // a/e/r/s/q from enrich_session.
          promptRoleRef.current = "enrich_choice";
        } else if (msg.choices.includes("y") && msg.choices.includes("f")) {
          promptRoleRef.current = "approval_choice";
        } else {
          promptRoleRef.current = "approval_choice";
        }
        s.setPending({ ...msg, kind: "choose" });
        return;
      case "text":
        if (msg.message.includes("Why not")) {
          promptRoleRef.current = "approval_reason";
        } else if (msg.message.includes("What should change")) {
          promptRoleRef.current = "approval_feedback";
          s.setPhase("fixing");
        } else if (msg.message.includes("Your wording")) {
          promptRoleRef.current = "enrich_edit";
        } else {
          // Generic text input — most likely an enrichment answer.
          promptRoleRef.current = "enrich_answer";
        }
        s.setPending({ ...msg, kind: "text" });
        return;
      case "done":
        s.setResult(msg.result);
        return;
      case "error":
        s.setError(msg.message);
        return;
    }
  }, []);

  const ws = useFlowSocket({
    onMessage: handleMessage,
    onClose: (ev) => {
      const s = sessionRef.current;
      if (s.phase !== "done" && s.phase !== "error") {
        s.setError(`WebSocket closed (code ${ev.code}).`);
      }
    },
  });

  // --- public API ----------------------------------------------------------

  // Send the StartMessage as soon as the socket opens. We can't send
  // before then — the socket buffers nothing pre-OPEN.
  const startedRef = useRef<StartParams | null>(null);
  useEffect(() => {
    if (ws.status === "open" && startedRef.current) {
      ws.send({ type: "start", params: startedRef.current });
      startedRef.current = null;
      sessionRef.current.setPhase("running");
    }
  }, [ws.status, ws]);

  const beginRun = useCallback(
    (params: StartParams) => {
      startedRef.current = params;
      sessionRef.current.reset();
      sessionRef.current.setPhase("starting");
      ws.connect("/api/ws/run");
    },
    [ws],
  );

  const reply = useCallback(
    (value: string | boolean) => {
      const s = sessionRef.current;
      ws.send({ type: "reply", value });
      s.setPending(null);
      promptRoleRef.current = null;
    },
    [ws],
  );

  /** Answer the "Accept this tailored version?" iteration prompt. */
  const acceptIteration = useCallback(() => reply(true), [reply]);
  const rejectIteration = useCallback(() => reply(false), [reply]);

  /** Answer the "Continue anyway?" cap prompt — yes resets, no exits. */
  const continuePastCap = useCallback(() => reply(true), [reply]);
  const stopPastCap = useCallback(() => reply(false), [reply]);

  /** Y/N/F/Q on a single proposal in the approval flow. */
  const acceptProposal = useCallback(() => {
    const proposal = sessionRef.current.currentProposal;
    if (proposal) sessionRef.current.recordApproved(proposal);
    reply("y");
  }, [reply]);

  const beginRejectProposal = useCallback(() => reply("n"), [reply]);

  const sendRejectionReason = useCallback(
    (reason: string) => {
      const proposal = sessionRef.current.currentProposal;
      if (proposal) {
        sessionRef.current.recordRejected(proposal, reason);
      }
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

  /** Enrichment offer panel — accept / decline. */
  const acceptEnrichOffer = useCallback(() => reply("y"), [reply]);
  const declineEnrichOffer = useCallback(() => reply("n"), [reply]);

  /** Enrichment a/e/r/s/q on a polished bullet. */
  const acceptEnrich = useCallback(() => {
    const polished = sessionRef.current.currentPolished;
    if (polished) sessionRef.current.recordAcceptedEnrich(polished);
    reply("a");
  }, [reply]);
  const editEnrich = useCallback(() => reply("e"), [reply]);
  const rejectEnrich = useCallback(() => reply("r"), [reply]);
  const skipEnrich = useCallback(() => reply("s"), [reply]);
  const quitEnrich = useCallback(() => reply("q"), [reply]);

  /** Send a text answer (enrichment question / edit / quit). */
  const sendText = useCallback((text: string) => reply(text), [reply]);

  return {
    status: ws.status,
    errorMsg: ws.errorMsg,
    promptRole: promptRoleRef.current,

    beginRun,
    disconnect: ws.disconnect,

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
