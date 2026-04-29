import { useEffect } from "react";

import { useTaskStore } from "./task-store";

/**
 * Mounted once at the app root — pulls the persisted task list on boot
 * and on window-focus so navigating in or out of the desktop shell
 * always lands on a fresh history. The list is the source of truth
 * for the sidebar; per-task live updates flow through `attach`.
 */
export function TaskHydrator() {
  const hydrate = useTaskStore((s) => s.hydrate);

  useEffect(() => {
    void hydrate();
    const onFocus = () => {
      void hydrate();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [hydrate]);

  return null;
}
