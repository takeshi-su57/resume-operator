import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { TaskList } from "@/components/task-list";
import { useTaskStore } from "@/state/task-store";

/**
 * `/score` — task list for score tasks. Same structure as the run
 * list: active section pinned, history below, click-through to detail,
 * trash button on terminal tasks.
 */
export function ScoreListScreen() {
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
      kind="score"
      onSelect={(id) => navigate(`/score/${id}`)}
      onDelete={deleteTask}
      onNew={() => navigate("/score/new")}
      newLabel="New score"
    />
  );
}
