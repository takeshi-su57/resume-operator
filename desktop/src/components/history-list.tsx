import { Trash2 } from "lucide-react";

import { RevealInFolderButton } from "@/components/reveal-in-folder-button";
import { Button } from "@/components/ui/button";
import { YamlPreviewDialog } from "@/components/yaml-preview-dialog";
import {
  useHistoryActions,
  useHistoryEntries,
  type HistoryPage,
} from "@/state/history";

type Props = {
  page: HistoryPage;
  title: string;
  /** Called when the user clicks an entry's source/output filename — lets the parent
   * pre-fill the form with the previous run's inputs. */
  onPick?: (entry: { source: string; output: string }) => void;
};

/**
 * Shared "recent runs" panel for pages that produce a file from a file
 * (Bootstrap, Extract Style). Backed by `state/history` (persisted to
 * localStorage). Each entry exposes both paths with a Reveal-in-Folder
 * button so Bruno can jump to the source .docx/.pdf or the produced
 * YAML without re-typing paths.
 *
 * Clicking the filename text re-uses the entry as form input via the
 * optional `onPick` callback — quick way to re-run an extraction
 * after editing the source file.
 */
export function HistoryList({ page, title, onPick }: Props) {
  const entries = useHistoryEntries(page);
  const { remove, clear } = useHistoryActions();

  if (entries.length === 0) return null;

  return (
    <section className="panel">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
        <h3 className="text-xs uppercase tracking-wider text-fg-muted">
          {title}
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => clear(page)}
          title={`Clear ${title.toLowerCase()}`}
        >
          Clear
        </Button>
      </div>
      <ul className="divide-y divide-border-subtle">
        {entries.map((entry) => (
          <li
            key={entry.at}
            className="flex flex-col gap-1.5 px-3 py-2.5 text-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-fg-faint">{relativeTime(entry.at)}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => remove(page, entry.at)}
                title="Remove from history"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
            <PathRow
              label="Source"
              path={entry.source}
              onPick={onPick ? () => onPick(entry) : undefined}
            />
            <PathRow
              label="Output"
              path={entry.output}
              onPick={onPick ? () => onPick(entry) : undefined}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

function PathRow({
  label,
  path,
  onPick,
}: {
  label: string;
  path: string;
  onPick?: () => void;
}) {
  const isYaml = /\.ya?ml$/i.test(path);
  return (
    <div className="grid grid-cols-[60px_1fr_auto] items-center gap-2">
      <span className="text-xs uppercase tracking-wider text-fg-muted">
        {label}
      </span>
      <button
        type="button"
        onClick={onPick}
        className="font-mono text-xs text-fg-muted hover:text-fg text-left truncate"
        title={onPick ? `Re-use this path: ${path}` : path}
        disabled={!onPick}
      >
        {basename(path)}
      </button>
      <div className="flex items-center gap-0.5">
        {isYaml && <YamlPreviewDialog path={path} iconOnly />}
        <RevealInFolderButton path={path} label="" />
      </div>
    </div>
  );
}

function basename(path: string): string {
  const m = path.match(/[^/\\]+$/);
  return m ? m[0] : path;
}

function relativeTime(epochMs: number): string {
  const seconds = Math.floor((Date.now() - epochMs) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86_400)}d ago`;
}
