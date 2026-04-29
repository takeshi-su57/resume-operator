import { ArrowLeft, RotateCcw, Trash2, XCircle } from "lucide-react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { AtsReport } from "@/components/ats-report";
import { TaskProgress } from "@/components/task-progress";
import { Button } from "@/components/ui/button";
import type { ATSReport, MasterView, ScoreRequest } from "@/lib/api";
import { useTaskStore } from "@/state/task-store";

type Props = {
  taskId: string;
};

/**
 * `/score/:taskId` — score detail. Attaches the live event stream;
 * while running, shows the unified `TaskProgress` widget; once the
 * task completes, swaps to the existing `AtsReport`. The user can
 * navigate away mid-score and come back to either the live progress
 * (if still running) or the cached result (if finished).
 */
export function ScoreDetailScreen({ taskId }: Props) {
  const task = useTaskStore((s) => s.tasks[taskId]);
  const attach = useTaskStore((s) => s.attach);
  const detach = useTaskStore((s) => s.detach);
  const cancelTask = useTaskStore((s) => s.cancelTask);
  const deleteTask = useTaskStore((s) => s.deleteTask);
  const startScore = useTaskStore((s) => s.startScore);
  const navigate = useNavigate();

  useEffect(() => {
    attach(taskId);
    return () => detach(taskId);
  }, [taskId, attach, detach]);

  if (!task) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-fg-faint">
        <p>Task not found.</p>
        <Button variant="ghost" size="sm" onClick={() => navigate("/score")}>
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to scores
        </Button>
      </div>
    );
  }

  const isRunning = task.status === "queued" || task.status === "running";
  const result = task.result as
    | { ats_score?: ATSReport; errors?: string[]; master_view?: MasterView | null }
    | null;

  return (
    <div className="grid h-full grid-cols-[280px_1fr]">
      <aside className="border-r border-border bg-bg-panel overflow-y-auto p-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/score")}
          className="mb-3"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          All scores
        </Button>
        <TaskProgress task={task} />
        {task.error && (
          <div className="mt-4 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
            {task.error}
          </div>
        )}
        <div className="mt-4 flex flex-col gap-1.5">
          {isRunning && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => cancelTask(taskId)}
            >
              <XCircle className="h-3.5 w-3.5" />
              Cancel
            </Button>
          )}
          {task.status === "interrupted" && (
            <Button
              variant="primary"
              size="sm"
              onClick={async () => {
                const params = task.params as unknown as ScoreRequest;
                const newId = await startScore(params);
                navigate(`/score/${newId}`, { replace: true });
              }}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Restart with same inputs
            </Button>
          )}
          {!isRunning && (
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                await deleteTask(taskId);
                navigate("/score");
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete from history
            </Button>
          )}
        </div>
      </aside>

      <section className="overflow-y-auto p-6">
        {result?.ats_score ? (
          <AtsReport
            report={result.ats_score}
            master={result.master_view ?? null}
          />
        ) : (
          <EmptyState status={task.status} />
        )}
      </section>
    </div>
  );
}

function EmptyState({ status }: { status: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center text-sm text-fg-faint">
      {status === "running" || status === "queued" ? (
        <p>Computing your score… progress on the left.</p>
      ) : status === "failed" ? (
        <p>Score failed — see the error on the left.</p>
      ) : status === "cancelled" ? (
        <p>Score cancelled.</p>
      ) : status === "interrupted" ? (
        <p>Sidecar restarted before this score finished.</p>
      ) : (
        <p>No result yet.</p>
      )}
    </div>
  );
}
