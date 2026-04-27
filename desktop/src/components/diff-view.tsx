import { diffWordsWithSpace } from "diff";
import { useMemo } from "react";

import { cn } from "@/lib/cn";

type DiffViewProps = {
  original: string;
  proposed: string;
  className?: string;
};

/**
 * Word-level diff with red strikethrough for removed text and green
 * highlight for added text. Inline (not split-pane) so the "before"
 * and "after" read like one polished sentence with its edits visible
 * in place.
 */
export function DiffView({ original, proposed, className }: DiffViewProps) {
  const parts = useMemo(
    () => diffWordsWithSpace(original ?? "", proposed ?? ""),
    [original, proposed],
  );
  return (
    <pre
      className={cn(
        "whitespace-pre-wrap break-words font-mono text-sm leading-relaxed",
        className,
      )}
    >
      {parts.map((part, i) => {
        if (part.added) {
          return (
            <span
              key={i}
              className="rounded-sm bg-success/15 text-success px-0.5"
            >
              {part.value}
            </span>
          );
        }
        if (part.removed) {
          return (
            <span
              key={i}
              className="rounded-sm bg-danger/15 text-danger line-through px-0.5"
            >
              {part.value}
            </span>
          );
        }
        return (
          <span key={i} className="text-fg-muted">
            {part.value}
          </span>
        );
      })}
    </pre>
  );
}
