/**
 * WebSocket protocol types — mirrors `src/resume_operator/server/ws_prompter.py`.
 *
 * Server-to-client messages drive the UI; client-to-server messages
 * carry user decisions back. Hand-mirrored for now (no codegen) — any
 * drift surfaces as a TS compile error in the dispatcher, since each
 * branch of `ServerMessage` has a discriminator on `type`.
 */

// --- Domain shapes carried by server messages ------------------------------

export type ProposalKind =
  | "rewrite_master"
  | "rewrite_fact"
  | "new_fact"
  | "new_skill";

export type Proposal = {
  kind: ProposalKind;
  grounding_source_id: string;
  original_text: string;
  proposed_text: string;
  rationale: string;
  target_role_id?: string;
};

export type EnrichQuestion = {
  area: string;
  question: string;
  why: string;
};

export type EnrichPolished = {
  polished_text: string;
  bucket: "project" | "extra_bullet" | "skill" | "certification";
  role_id: string;
};

// --- Server → client messages ----------------------------------------------

export type NodeEventMessage = {
  type: "node_event";
  node: string;
  phase: "start" | "end" | "error" | "progress";
  data: Record<string, unknown>;
  timestamp: number;
};

export type ProgressEventData = {
  step: string;
  label: string;
  detail?: Record<string, unknown>;
};

export type ConfirmMessage = {
  type: "confirm";
  message: string;
  default: boolean;
};

export type ChooseMessage = {
  type: "choose";
  message: string;
  choices: string[];
  default: string;
};

export type TextMessage = {
  type: "text";
  message: string;
  default: string;
};

export type RenderProposalMessage = {
  type: "render_proposal";
  proposal: Proposal;
  index: number;
  total: number;
};

export type RenderIterationHeaderMessage = {
  type: "render_iteration_header";
  iteration: number;
  max_iter: number;
  score: number;
};

export type RenderQuestionMessage = {
  type: "render_question";
  question: EnrichQuestion;
  index: number;
  total: number;
};

export type RenderPolishedMessage = {
  type: "render_polished";
  polished: EnrichPolished;
};

export type NoticeMessage = {
  type: "notice";
  message: string;
  style: string;
};

export type PanelMessage = {
  type: "panel";
  message: string;
  title: string;
  style: string;
};

export type StatusStartMessage = {
  type: "status_start";
  message: string;
  at: number;
};

export type StatusEndMessage = {
  type: "status_end";
  at: number;
};

export type DoneMessage = {
  type: "done";
  result: Record<string, unknown>;
};

export type ErrorMessage = {
  type: "error";
  message: string;
};

// --- Task-stream framing (Phase 2 task registry) ---------------------------

export type PendingPromptShape = {
  kind: "confirm" | "choose" | "text";
  prompt_seq: number;
  message: string;
  default?: string | number | boolean | null;
  choices?: string[] | null;
};

export type TaskKind = "run" | "score";
export type TaskStatus =
  | "queued"
  | "running"
  | "awaiting_input"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

/**
 * Server-side `Task` snapshot. Mirrors `lucky_resume.server.tasks.model.Task`.
 * The `events` list is the full append-only log — replaying it re-creates
 * the live UI state.
 */
export type TaskSnapshot = {
  id: string;
  kind: TaskKind;
  status: TaskStatus;
  params: Record<string, unknown>;
  events: Array<Record<string, unknown>>;
  pending_prompt: PendingPromptShape | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: number;
  started_at: number | null;
  ended_at: number | null;
  schema_version: number;
};

export type SnapshotMessage = {
  type: "snapshot";
  task: TaskSnapshot;
};

export type TaskStatusMessage = {
  type: "task_status";
  status: TaskStatus;
  pending_prompt: PendingPromptShape | null;
  result: Record<string, unknown> | null;
  error: string | null;
  started_at: number | null;
  ended_at: number | null;
};

export type ConfirmMessageWithSeq = ConfirmMessage & { prompt_seq?: number };
export type ChooseMessageWithSeq = ChooseMessage & { prompt_seq?: number };
export type TextMessageWithSeq = TextMessage & { prompt_seq?: number };

export type ServerMessage =
  | SnapshotMessage
  | TaskStatusMessage
  | NodeEventMessage
  | ConfirmMessageWithSeq
  | ChooseMessageWithSeq
  | TextMessageWithSeq
  | RenderProposalMessage
  | RenderIterationHeaderMessage
  | RenderQuestionMessage
  | RenderPolishedMessage
  | NoticeMessage
  | PanelMessage
  | StatusStartMessage
  | StatusEndMessage
  | DoneMessage
  | ErrorMessage;

// --- Client → server messages ----------------------------------------------

export type StartMessage = {
  type: "start";
  params: Record<string, unknown>;
};

export type ReplyMessage = {
  type: "reply";
  /** When attached to a task stream, scope the reply to a specific
   * pending prompt — guards against stale replies from a previous
   * prompt the consumer didn't see resolve. */
  prompt_seq?: number;
  value: string | boolean | number;
};

export type CancelMessage = {
  type: "cancel";
};

export type ClientMessage = StartMessage | ReplyMessage | CancelMessage;

// --- Type-narrowing helpers ------------------------------------------------

export function isPromptMessage(
  m: ServerMessage,
): m is ConfirmMessage | ChooseMessage | TextMessage {
  return m.type === "confirm" || m.type === "choose" || m.type === "text";
}
