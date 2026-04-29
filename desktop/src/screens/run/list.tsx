import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { TaskList } from "@/components/task-list";
import { useTaskStore } from "@/state/task-store";

/**
 * `/run` — task list. Shows active runs (running / awaiting input /
 * queued) pinned to the top, history (completed / failed / cancelled
 * / interrupted) below. Clicking a row navigates into its detail
 * view. "New run" navigates to the inputs form.
 */
export function RunListScreen() {
  // Select the stable map reference; deriving the array inside the
  // selector returns a fresh `Object.values(...)` each call and trips
  // useSyncExternalStore into an infinite re-render loop.
  const taskMap = useTaskStore((s) => s.tasks);
  const tasks = useMemo(() => Object.values(taskMap), [taskMap]);
  const deleteTask = useTaskStore((s) => s.deleteTask);
  const navigate = useNavigate();

  return (
    <TaskList
      tasks={tasks}
      kind="run"
      onSelect={(id) => navigate(`/run/${id}`)}
      onDelete={deleteTask}
      onNew={() => navigate("/run/new")}
      newLabel="New run"
    />
  );
}
