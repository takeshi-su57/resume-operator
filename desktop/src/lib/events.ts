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
  phase: "start" | "end" | "error";
  data: Record<string, unknown>;
  timestamp: number;
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

export type ServerMessage =
  | NodeEventMessage
  | ConfirmMessage
  | ChooseMessage
  | TextMessage
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
  value: string | boolean | number;
};

export type ClientMessage = StartMessage | ReplyMessage;

// --- Type-narrowing helpers ------------------------------------------------

export function isPromptMessage(
  m: ServerMessage,
): m is ConfirmMessage | ChooseMessage | TextMessage {
  return m.type === "confirm" || m.type === "choose" || m.type === "text";
}
