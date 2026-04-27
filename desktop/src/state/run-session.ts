import { create } from "zustand";

import type {
  ChooseMessage,
  ConfirmMessage,
  EnrichPolished,
  EnrichQuestion,
  Proposal,
  TextMessage,
} from "@/lib/events";

/**
 * The Run session is a finite-ish state machine driven by the server's
 * WebSocket protocol. It splits into three concerns:
 *
 *   - `phase` — what the user is currently looking at (inputs / running
 *     / iteration-confirm / approval / enrich / done / error).
 *   - `pendingPrompt` — the open server question the user must answer
 *     for the flow to advance. UI shows the corresponding panel.
 *   - Append-only logs (`nodeEvents`, `iterationHistory`,
 *     `approvedProposals`, `rejectedProposals`, `acceptedEnrichItems`)
 *     that fill the side panels and tell the story across iterations.
 *
 * The store is intentionally side-effect-free — the route handlers
 * own the WebSocket; this just buffers what the UI needs.
 */

export type RunPhase =
  | "idle"
  | "starting"
  | "running"
  | "iteration_confirm"
  | "approval"
  | "enrich_question"
  | "enrich_polished"
  | "fixing"
  | "done"
  | "error";

export type NodeStep = {
  node: string;
  phase: "start" | "end" | "error";
  timestamp: number;
  data: Record<string, unknown>;
};

export type IterationLog = {
  iteration: number;
  maxIter: number;
  score: number;
  at: number;
};

export type StatusStep = {
  message: string;
  startedAt: number;
  endedAt: number | null;
};

export type PendingPrompt =
  | (ConfirmMessage & { kind: "confirm" })
  | (ChooseMessage & { kind: "choose" })
  | (TextMessage & { kind: "text" })
  | null;

export type RunSessionState = {
  phase: RunPhase;
  errorMessage: string | null;

  // Pipeline progress signals.
  nodeEvents: NodeStep[];
  iterationHistory: IterationLog[];
  statusStack: StatusStep[];

  // Iteration display.
  currentIteration: number | null;
  currentMaxIter: number | null;
  currentScore: number | null;

  // Approval-loop state.
  currentProposal: Proposal | null;
  proposalIndex: number; // 1-indexed
  proposalTotal: number;
  approvedProposals: Proposal[];
  rejectedProposals: { proposal: Proposal; reason: string }[];

  // Enrichment state.
  currentQuestion: EnrichQuestion | null;
  questionIndex: number;
  questionTotal: number;
  currentPolished: EnrichPolished | null;
  acceptedEnrichItems: EnrichPolished[];

  // Open prompt the user must answer.
  pendingPrompt: PendingPrompt;

  // Final output.
  result: Record<string, unknown> | null;
};

type RunSessionActions = {
  reset: () => void;
  setPhase: (phase: RunPhase) => void;
  setError: (message: string) => void;

  pushNodeEvent: (event: NodeStep) => void;
  pushIteration: (log: IterationLog) => void;
  setProposal: (proposal: Proposal, index: number, total: number) => void;
  setQuestion: (
    question: EnrichQuestion,
    index: number,
    total: number,
  ) => void;
  setPolished: (polished: EnrichPolished | null) => void;
  setPending: (prompt: PendingPrompt) => void;

  pushStatusStart: (message: string, startedAt: number) => void;
  pushStatusEnd: (endedAt: number) => void;

  recordApproved: (proposal: Proposal) => void;
  recordRejected: (proposal: Proposal, reason: string) => void;
  recordAcceptedEnrich: (polished: EnrichPolished) => void;

  setResult: (result: Record<string, unknown>) => void;
};

const initial: RunSessionState = {
  phase: "idle",
  errorMessage: null,
  nodeEvents: [],
  iterationHistory: [],
  statusStack: [],
  currentIteration: null,
  currentMaxIter: null,
  currentScore: null,
  currentProposal: null,
  proposalIndex: 0,
  proposalTotal: 0,
  approvedProposals: [],
  rejectedProposals: [],
  currentQuestion: null,
  questionIndex: 0,
  questionTotal: 0,
  currentPolished: null,
  acceptedEnrichItems: [],
  pendingPrompt: null,
  result: null,
};

export const useRunSession = create<RunSessionState & RunSessionActions>(
  (set) => ({
    ...initial,

    reset: () => set(initial),
    setPhase: (phase) => set({ phase }),
    setError: (message) => set({ phase: "error", errorMessage: message }),

    pushNodeEvent: (event) =>
      set((s) => ({ nodeEvents: [...s.nodeEvents, event] })),

    pushIteration: (log) =>
      set((s) => ({
        iterationHistory: [...s.iterationHistory, log],
        currentIteration: log.iteration,
        currentMaxIter: log.maxIter,
        currentScore: log.score,
      })),

    setProposal: (proposal, index, total) =>
      set({
        currentProposal: proposal,
        proposalIndex: index,
        proposalTotal: total,
        phase: "approval",
      }),

    setQuestion: (question, index, total) =>
      set({
        currentQuestion: question,
        questionIndex: index,
        questionTotal: total,
        currentPolished: null,
        phase: "enrich_question",
      }),

    setPolished: (polished) =>
      set({
        currentPolished: polished,
        phase: polished ? "enrich_polished" : "enrich_question",
      }),

    setPending: (prompt) => set({ pendingPrompt: prompt }),

    pushStatusStart: (message, startedAt) =>
      set((s) => ({
        statusStack: [...s.statusStack, { message, startedAt, endedAt: null }],
      })),

    pushStatusEnd: (endedAt) =>
      set((s) => {
        const next = [...s.statusStack];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].endedAt === null) {
            next[i] = { ...next[i], endedAt };
            break;
          }
        }
        return { statusStack: next };
      }),

    recordApproved: (proposal) =>
      set((s) => ({ approvedProposals: [...s.approvedProposals, proposal] })),

    recordRejected: (proposal, reason) =>
      set((s) => ({
        rejectedProposals: [...s.rejectedProposals, { proposal, reason }],
      })),

    recordAcceptedEnrich: (polished) =>
      set((s) => ({
        acceptedEnrichItems: [...s.acceptedEnrichItems, polished],
      })),

    setResult: (result) => set({ result, phase: "done" }),
  }),
);
