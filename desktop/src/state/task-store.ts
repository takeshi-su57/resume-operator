import { create } from "zustand";

import {
  cancelTask as apiCancel,
  deleteTask as apiDelete,
  listTasks,
  replyTask as apiReply,
  serverWsUrl,
  startRun as apiStartRun,
  startScore as apiStartScore,
  type RunRequest,
  type ScoreRequest,
} from "@/lib/api";
import type {
  ServerMessage,
  TaskSnapshot,
  TaskStatus,
} from "@/lib/events";

/**
 * Multi-task store — the single source of truth for the desktop's view
 * of registered backend tasks.
 *
 * Survives navigation. The Tauri shell mounts the app once; the store
 * lives for the app's lifetime, and screens are thin selectors over it.
 *
 * Three distinct event channels feed the store:
 *
 *   - `hydrate()` (or React Query's `useTasks`) pulls the full list
 *     from `GET /api/tasks` on app boot and after destructive ops.
 *   - `attach(id)` opens a WS to `/api/tasks/{id}/stream`. The first
 *     frame is always a `snapshot` carrying the full task; subsequent
 *     frames are events the snapshot didn't include yet. Both feed
 *     `applySnapshot` and `applyEvent` respectively.
 *   - User actions (`startRun`, `startScore`, `cancelTask`,
 *     `deleteTask`, `reply`) hit the corresponding HTTP endpoints; the
 *     responses (or subsequent WS frames) feed the store.
 *
 * Detaching the WS does **not** cancel the task — that's the point of
 * the registry. The user can navigate away, come back hours later, and
 * pick up where the snapshot left off.
 */

export type AttachStatus = "idle" | "connecting" | "open" | "closed" | "error";

export type AttachState = {
  status: AttachStatus;
  socket: WebSocket | null;
  errorMessage: string | null;
};

const idleAttach: AttachState = { status: "idle", socket: null, errorMessage: null };

type TaskMap = Record<string, TaskSnapshot>;

type TaskStoreState = {
  tasks: TaskMap;
  attachments: Record<string, AttachState>;
  hydratedAt: number | null;
};

type TaskStoreActions = {
  hydrate: () => Promise<void>;
  attach: (taskId: string) => void;
  detach: (taskId: string) => void;
  upsert: (task: TaskSnapshot) => void;
  remove: (taskId: string) => void;
  startRun: (params: RunRequest) => Promise<string>;
  startScore: (params: ScoreRequest) => Promise<string>;
  cancelTask: (taskId: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  reply: (
    taskId: string,
    promptSeq: number,
    value: string | boolean | number,
  ) => void;
};

export const useTaskStore = create<TaskStoreState & TaskStoreActions>(
  (set, get) => ({
    tasks: {},
    attachments: {},
    hydratedAt: null,

    hydrate: async () => {
      const list = await listTasks();
      const tasks: TaskMap = {};
      for (const t of list) tasks[t.id] = t;
      set({ tasks, hydratedAt: Date.now() });
    },

    upsert: (task) =>
      set((s) => ({ tasks: { ...s.tasks, [task.id]: task } })),

    remove: (taskId) =>
      set((s) => {
        const { [taskId]: _, ...rest } = s.tasks;
        return { tasks: rest };
      }),

    attach: (taskId) => {
      const existing = get().attachments[taskId];
      if (existing && (existing.status === "open" || existing.status === "connecting")) {
        // Already attached — skip the duplicate WS.
        return;
      }
      const socket = new WebSocket(
        serverWsUrl(`/api/tasks/${encodeURIComponent(taskId)}/stream`),
      );
      set((s) => ({
        attachments: {
          ...s.attachments,
          [taskId]: { status: "connecting", socket, errorMessage: null },
        },
      }));

      socket.onopen = () => {
        set((s) => ({
          attachments: {
            ...s.attachments,
            [taskId]: { status: "open", socket, errorMessage: null },
          },
        }));
      };
      socket.onclose = () => {
        set((s) => {
          const cur = s.attachments[taskId];
          if (!cur || cur.socket !== socket) return s;
          return {
            attachments: {
              ...s.attachments,
              [taskId]: { ...cur, status: "closed", socket: null },
            },
          };
        });
      };
      socket.onerror = () => {
        set((s) => {
          const cur = s.attachments[taskId] ?? idleAttach;
          return {
            attachments: {
              ...s.attachments,
              [taskId]: {
                ...cur,
                status: "error",
                errorMessage: "WebSocket error",
              },
            },
          };
        });
      };
      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as ServerMessage;
          applyMessage(get, set, taskId, msg);
        } catch (err) {
          console.error("task-store: bad WS message", err, ev.data);
        }
      };
    },

    detach: (taskId) => {
      const att = get().attachments[taskId];
      if (att?.socket) {
        att.socket.close();
      }
      set((s) => {
        const { [taskId]: _, ...rest } = s.attachments;
        return { attachments: rest };
      });
    },

    startRun: async (params) => {
      const { task_id } = await apiStartRun(params);
      // Seed an empty placeholder so the list renders the new task
      // immediately; the snapshot frame from `attach` will fill it in.
      const placeholder: TaskSnapshot = {
        id: task_id,
        kind: "run",
        status: "queued",
        params: params as unknown as Record<string, unknown>,
        events: [],
        pending_prompt: null,
        result: null,
        error: null,
        created_at: Date.now() / 1000,
        started_at: null,
        ended_at: null,
        schema_version: 1,
      };
      set((s) => ({ tasks: { ...s.tasks, [task_id]: placeholder } }));
      return task_id;
    },

    startScore: async (params) => {
      const { task_id } = await apiStartScore(params);
      const placeholder: TaskSnapshot = {
        id: task_id,
        kind: "score",
        status: "queued",
        params: params as unknown as Record<string, unknown>,
        events: [],
        pending_prompt: null,
        result: null,
        error: null,
        created_at: Date.now() / 1000,
        started_at: null,
        ended_at: null,
        schema_version: 1,
      };
      set((s) => ({ tasks: { ...s.tasks, [task_id]: placeholder } }));
      return task_id;
    },

    cancelTask: async (taskId) => {
      await apiCancel(taskId);
    },

    deleteTask: async (taskId) => {
      await apiDelete(taskId);
      set((s) => {
        const { [taskId]: _t, ...rest } = s.tasks;
        const { [taskId]: _a, ...restAtt } = s.attachments;
        return { tasks: rest, attachments: restAtt };
      });
    },

    reply: (taskId, promptSeq, value) => {
      const att = get().attachments[taskId];
      if (att?.socket && att.status === "open") {
        att.socket.send(
          JSON.stringify({ type: "reply", prompt_seq: promptSeq, value }),
        );
        return;
      }
      // Fallback: HTTP reply if no live WS (shouldn't happen in normal
      // navigation, but covers the case where the user reopens a paused
      // task before reattaching).
      void apiReply(taskId, promptSeq, value);
    },
  }),
);

function applyMessage(
  get: () => TaskStoreState & TaskStoreActions,
  set: (
    updater: (
      s: TaskStoreState & TaskStoreActions,
    ) => Partial<TaskStoreState & TaskStoreActions>,
  ) => void,
  taskId: string,
  msg: ServerMessage,
) {
  if (msg.type === "snapshot") {
    set((s) => ({ tasks: { ...s.tasks, [msg.task.id]: msg.task } }));
    return;
  }
  if (msg.type === "task_status") {
    const cur = get().tasks[taskId];
    if (!cur) return;
    set((s) => ({
      tasks: {
        ...s.tasks,
        [taskId]: {
          ...cur,
          status: msg.status as TaskStatus,
          pending_prompt: msg.pending_prompt,
          result: msg.result,
          error: msg.error,
          started_at: msg.started_at,
          ended_at: msg.ended_at,
        },
      },
    }));
    return;
  }
  // Everything else is a wire event the backend already added to its
  // log; mirror it locally so selectors that read `task.events` see it.
  const cur = get().tasks[taskId];
  if (!cur) return;
  set((s) => ({
    tasks: {
      ...s.tasks,
      [taskId]: {
        ...cur,
        events: [...cur.events, msg as unknown as Record<string, unknown>],
        // Track pending prompt locally so the UI can reflect it without
        // waiting for a separate `task_status` frame.
        pending_prompt:
          msg.type === "confirm" ||
          msg.type === "choose" ||
          msg.type === "text"
            ? {
                kind: msg.type,
                prompt_seq: (msg as { prompt_seq?: number }).prompt_seq ?? 0,
                message: msg.message,
                default:
                  "default" in msg
                    ? (msg as { default?: unknown }).default as
                        | string
                        | number
                        | boolean
                        | null
                        | undefined ?? null
                    : null,
                choices:
                  msg.type === "choose"
                    ? (msg as { choices: string[] }).choices
                    : null,
              }
            : cur.pending_prompt,
      },
    },
  }));
}
