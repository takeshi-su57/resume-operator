import { Plus } from "lucide-react";
import { useMemo } from "react";

import { TaskCard } from "@/components/task-card";
import { Button } from "@/components/ui/button";
import type { TaskKind, TaskSnapshot } from "@/lib/events";

const ACTIVE_STATUSES = new Set(["queued", "running", "awaiting_input"]);

type Props = {
  tasks: TaskSnapshot[];
  kind: TaskKind;
  activeId?: string | null;
  onSelect: (taskId: string) => void;
  onDelete: (taskId: string) => void;
  onNew: () => void;
  newLabel?: string;
};

/**
 * Two-section task panel — Active (running / awaiting input / queued)
 * pinned to the top, History (everything else, newest first) below.
 *
 * Used by both the Run and Score screens with a different `kind`
 * filter. Keeps the visual shape consistent so navigating between
 * Run and Score doesn't disorient the user.
 */
export function TaskList({
  tasks,
  kind,
  activeId,
  onSelect,
  onDelete,
  onNew,
  newLabel,
}: Props) {
  const filtered = useMemo(
    () => tasks.filter((t) => t.kind === kind),
    [tasks, kind],
  );
  const active = useMemo(
    () => filtered.filter((t) => ACTIVE_STATUSES.has(t.status)),
    [filtered],
  );
  const history = useMemo(
    () => filtered.filter((t) => !ACTIVE_STATUSES.has(t.status)),
    [filtered],
  );

  return (
    <div className="flex h-full flex-col overflow-y-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-wide text-fg-dim">
          {kind === "score" ? "Score Tasks" : "Run Tasks"}
        </h2>
        <Button variant="primary" size="sm" onClick={onNew}>
          <Plus className="h-3.5 w-3.5" />
          {newLabel ?? "New"}
        </Button>
      </div>

      {active.length > 0 && (
        <Section
          title="Active"
          tasks={active}
          activeId={activeId}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      )}

      {history.length > 0 ? (
        <Section
          title="History"
          tasks={history}
          activeId={activeId}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ) : (
        active.length === 0 && (
          <div className="mt-8 rounded-md border border-dashed border-border p-6 text-center text-xs text-fg-faint">
            No {kind === "score" ? "scores" : "runs"} yet. Click {newLabel ?? "New"} to start one.
          </div>
        )
      )}
    </div>
  );
}

function Section({
  title,
  tasks,
  activeId,
  onSelect,
  onDelete,
}: {
  title: string;
  tasks: TaskSnapshot[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="mb-4">
      <h3 className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-wide text-fg-faint">
        {title}
      </h3>
      <div className="space-y-1.5">
        {tasks.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            active={t.id === activeId}
            onSelect={onSelect}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}
