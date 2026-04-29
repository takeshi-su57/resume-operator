import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Gauge,
  Hourglass,
  Loader2,
  PauseCircle,
  PlayCircle,
  Trash2,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { TaskKind, TaskSnapshot, TaskStatus } from "@/lib/events";

type Props = {
  task: TaskSnapshot;
  active?: boolean;
  onSelect?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
};

/**
 * One row in a task list. Renders the kind icon, status pill, the JD
 * file (most distinguishing input across runs), and timing. Clicking
 * the row navigates to detail; the trash button deletes (only enabled
 * for terminal tasks).
 */
export function TaskCard({ task, active, onSelect, onDelete }: Props) {
  const KindIcon = task.kind === "score" ? Gauge : PlayCircle;
  const isTerminal = TERMINAL.has(task.status);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect?.(task.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect?.(task.id);
      }}
      className={cn(
        "group flex items-center gap-3 rounded-md border border-border px-3 py-2 text-left",
        "cursor-pointer transition-colors",
        active
          ? "bg-bg-raised border-accent"
          : "bg-bg-panel hover:bg-bg-raised",
      )}
    >
      <KindIcon className="h-4 w-4 shrink-0 text-fg-dim" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-xs font-medium text-fg">
            {jobLabel(task) || `${kindLabel(task.kind)} task`}
          </span>
          <StatusPill status={task.status} />
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[0.6875rem] text-fg-faint">
          <Clock className="h-3 w-3" />
          <span>{formatTime(task.created_at)}</span>
          {task.ended_at && task.started_at && (
            <span>· {formatDuration(task.ended_at - task.started_at)}</span>
          )}
        </div>
      </div>
      {onDelete && (
        <Button
          variant="ghost"
          size="sm"
          aria-label="Delete task"
          disabled={!isTerminal}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(task.id);
          }}
          className="opacity-0 group-hover:opacity-100"
          title={
            isTerminal
              ? "Delete from history"
              : "Cancel the task before deleting"
          }
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
}

const TERMINAL = new Set<TaskStatus>([
  "completed",
  "failed",
  "cancelled",
  "interrupted",
]);

function StatusPill({ status }: { status: TaskStatus }) {
  const cfg = STATUS_CONFIG[status];
  const Icon = cfg.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5",
        "text-[0.625rem] font-medium uppercase tracking-wide",
        cfg.className,
      )}
    >
      <Icon
        className={cn("h-3 w-3", cfg.spin && "animate-spin")}
      />
      {cfg.label}
    </span>
  );
}

const STATUS_CONFIG: Record<
  TaskStatus,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    className: string;
    spin?: boolean;
  }
> = {
  queued: {
    label: "queued",
    icon: Hourglass,
    className: "bg-bg-raised text-fg-dim",
  },
  running: {
    label: "running",
    icon: Loader2,
    className: "bg-accent/15 text-accent",
    spin: true,
  },
  awaiting_input: {
    label: "awaiting",
    icon: PauseCircle,
    className: "bg-warn/15 text-warn",
  },
  completed: {
    label: "completed",
    icon: CheckCircle2,
    className: "bg-success/15 text-success",
  },
  failed: {
    label: "failed",
    icon: AlertCircle,
    className: "bg-danger/15 text-danger",
  },
  cancelled: {
    label: "cancelled",
    icon: XCircle,
    className: "bg-bg-raised text-fg-faint",
  },
  interrupted: {
    label: "interrupted",
    icon: AlertCircle,
    className: "bg-warn/15 text-warn",
  },
};

function jobLabel(task: TaskSnapshot): string {
  const job = (task.params as { job?: string }).job;
  if (!job) return "";
  const parts = job.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || job;
}

function kindLabel(kind: TaskKind): string {
  return kind === "score" ? "Score" : "Run";
}

function formatTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  const today = new Date();
  if (
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  ) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m${s.toString().padStart(2, "0")}s`;
}
