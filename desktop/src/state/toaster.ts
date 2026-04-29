/**
 * Toast queue — minimal store backing the bottom-right notifier.
 *
 * Pages call `notify(...)` from anywhere; the `<Toaster />` mounted in
 * App.tsx subscribes and renders the queue with Radix Toast. Each entry
 * auto-dismisses after `duration` ms or when the user closes it.
 */

import { create } from "zustand";

export type ToastKind = "success" | "error" | "info";

export type Toast = {
  id: number;
  kind: ToastKind;
  title: string;
  description?: string;
  /** Auto-dismiss timeout in ms. Defaults to 4000 for success/info, 8000 for error. */
  duration: number;
};

type ToasterState = {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id" | "duration"> & { duration?: number }) => void;
  dismiss: (id: number) => void;
};

let nextId = 1;

export const useToaster = create<ToasterState>((set) => ({
  toasts: [],
  push: (toast) =>
    set((state) => ({
      toasts: [
        ...state.toasts,
        {
          id: nextId++,
          duration:
            toast.duration ??
            (toast.kind === "error" ? 8000 : 4000),
          ...toast,
        },
      ],
    })),
  dismiss: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));

/**
 * Convenience: fire a toast from anywhere without grabbing the hook.
 * Components inside React can use `useToaster((s) => s.push)` instead.
 */
export function notify(toast: Parameters<ToasterState["push"]>[0]): void {
  useToaster.getState().push(toast);
}
