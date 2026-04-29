import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTaskStore } from "@/state/task-store";

import { RunInputs, type RunInputs as RunInputsType } from "./inputs";

/**
 * `/run/new` — pre-flight inputs. On submit, registers a new task
 * via `taskStore.startRun` and navigates to its detail view; the
 * detail view will attach to the live event stream.
 */
export function RunNewScreen() {
  const startRun = useTaskStore((s) => s.startRun);
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (inputs: RunInputsType) => {
    setSubmitting(true);
    setError(null);
    try {
      const taskId = await startRun(inputs);
      navigate(`/run/${taskId}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
      setSubmitting(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      {error && (
        <div className="mx-auto mt-4 max-w-2xl px-6">
          <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
            {error}
          </div>
        </div>
      )}
      <RunInputs onSubmit={onSubmit} disabled={submitting} />
    </div>
  );
}
