import { ArrowLeft } from "lucide-react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useTaskStore } from "@/state/task-store";

import { useRunController } from "./use-run-controller";
import { RunWorkspace } from "./workspace";

type Props = {
  taskId: string;
};

/**
 * `/run/:taskId` — detail view. Attaches the WebSocket stream on
 * mount, hands the controller to the existing three-pane workspace,
 * detaches on unmount. Detaching does NOT cancel the task — the user
 * can navigate away and come back later.
 */
export function RunDetailScreen({ taskId }: Props) {
  const task = useTaskStore((s) => s.tasks[taskId]);
  const attach = useTaskStore((s) => s.attach);
  const detach = useTaskStore((s) => s.detach);
  const navigate = useNavigate();
  const controller = useRunController(taskId);

  useEffect(() => {
    attach(taskId);
    return () => detach(taskId);
  }, [taskId, attach, detach]);

  if (!task) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-fg-faint">
        <p>Task not found.</p>
        <Button variant="ghost" size="sm" onClick={() => navigate("/run")}>
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to runs
        </Button>
      </div>
    );
  }

  return (
    <RunWorkspace
      controller={controller}
      onReset={() => navigate("/run")}
    />
  );
}
