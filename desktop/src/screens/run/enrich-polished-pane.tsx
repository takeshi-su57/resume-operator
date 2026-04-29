import { Check, Pencil, SkipForward, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { EnrichPolished } from "@/lib/events";
import { useRunSession } from "@/state/run-session";

type Props = {
  onAccept: () => void;
  onEdit: (text: string) => void;
  onReject: () => void;
  onSkip: () => void;
  onQuit: () => void;
};

const BUCKET_LABELS: Record<EnrichPolished["bucket"], string> = {
  project: "project",
  extra_bullet: "extra bullet",
  skill: "skill",
  certification: "certification",
};

const BUCKET_TONES: Record<EnrichPolished["bucket"], string> = {
  project: "border-accent/40 bg-accent/10 text-accent",
  extra_bullet: "border-success/40 bg-success/10 text-success",
  skill: "border-warning/40 bg-warning/10 text-warning",
  certification: "border-fg-muted/30 bg-bg-raised text-fg-muted",
};

/**
 * Polished bullet card — server has emitted `render_polished` with
 * the LLM's classification + role linkage and is waiting on a
 * choose-prompt with options a/e/r/s/q.
 *
 * "Accept" sends `a` and persists; "Edit" expands an inline textarea
 * pre-filled with the polished text — submit sends `e` followed by a
 * text reply containing the edited wording (the server's choose
 * prompt branches on `e`, then issues a new text prompt for "Your
 * wording", which our controller routes to `enrich_edit`).
 */
export function EnrichPolishedPane({
  onAccept,
  onEdit,
  onReject,
  onSkip,
  onQuit,
}: Props) {
  const polished = useRunSession((s) => s.currentPolished);
  const question = useRunSession((s) => s.currentQuestion);
  const index = useRunSession((s) => s.questionIndex);
  const total = useRunSession((s) => s.questionTotal);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // When a new polished bullet arrives, snap to non-editing mode.
  useEffect(() => {
    setEditing(false);
    setDraft(polished?.polished_text ?? "");
  }, [polished]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  if (!polished) return null;

  const submitEdit = () => {
    if (!draft.trim()) return;
    setEditing(false);
    onEdit(draft);
  };

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-border px-6 py-3">
        <p className="text-xs uppercase tracking-wider text-fg-muted">
          Enrichment · polished {index} / {total}
        </p>
        {question?.question && (
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            <span className="text-fg-faint">q:</span> {question.question}
          </p>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={cn(
              "rounded-md border px-2 py-0.5 text-xs font-mono",
              BUCKET_TONES[polished.bucket],
            )}
          >
            {BUCKET_LABELS[polished.bucket]}
          </span>
          {polished.role_id && (
            <span className="rounded-sm border border-border bg-bg-raised px-1.5 py-0.5 font-mono text-xs text-fg-dim">
              role: {polished.role_id}
            </span>
          )}
        </div>

        {editing ? (
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="input-base min-h-[140px] resize-none font-mono leading-relaxed"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitEdit();
              }
              if (e.key === "Escape") {
                e.preventDefault();
                setEditing(false);
                setDraft(polished.polished_text);
              }
            }}
          />
        ) : (
          <p className="font-mono text-sm leading-relaxed text-success bg-success/5 border border-success/20 rounded-md px-3 py-2">
            {polished.polished_text}
          </p>
        )}
      </div>

      <div
        className="border-t border-border px-6 py-2 flex items-center gap-2"
        data-no-select
      >
        {editing ? (
          <>
            <Button
              variant="primary"
              onClick={submitEdit}
              disabled={!draft.trim()}
              title="Save edit (Ctrl+Enter)"
            >
              <Check className="h-4 w-4" />
              Save edit
              <span className="kbd ml-1">Ctrl</span>
              <span className="kbd">⏎</span>
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setEditing(false);
                setDraft(polished.polished_text);
              }}
            >
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button variant="primary" onClick={onAccept} title="Accept (a)">
              <Check className="h-4 w-4" />
              Accept
              <span className="kbd ml-1">a</span>
            </Button>
            <Button
              variant="secondary"
              onClick={() => setEditing(true)}
              title="Edit wording (e)"
            >
              <Pencil className="h-4 w-4" />
              Edit
              <span className="kbd ml-1">e</span>
            </Button>
            <Button variant="secondary" onClick={onReject} title="Reject (r)">
              <X className="h-4 w-4" />
              Reject
              <span className="kbd ml-1">r</span>
            </Button>
            <Button variant="ghost" onClick={onSkip} title="Skip (s)">
              <SkipForward className="h-4 w-4" />
              Skip
              <span className="kbd ml-1">s</span>
            </Button>
            <div className="ml-auto">
              <Button variant="ghost" onClick={onQuit} title="Quit (q)">
                Quit
                <span className="kbd ml-1">q</span>
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
