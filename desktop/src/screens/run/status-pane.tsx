import { CheckCircle2, FolderOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useRunSession } from "@/state/run-session";

/**
 * Center pane terminal states — `done` and `error`. The done view
 * surfaces the output PDF path with a "show in folder" CTA; the
 * error view shows the message + a Reset CTA so the user can restart
 * without leaving the screen.
 */
export function StatusPane({ onReset }: { onReset: () => void }) {
  const phase = useRunSession((s) => s.phase);
  const result = useRunSession((s) => s.result);
  const errorMessage = useRunSession((s) => s.errorMessage);

  if (phase === "done") {
    const outputPath =
      typeof result?.output_path === "string" ? result.output_path : null;
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="w-full max-w-md panel p-6 space-y-4 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/15">
            <CheckCircle2 className="h-6 w-6 text-success" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-fg">Pipeline complete</h2>
            <p className="mt-1 text-xs text-fg-dim leading-relaxed">
              Tailored resume rendered to disk. Open the folder to inspect the
              PDF, tailored.yaml, diff.md, and results.json.
            </p>
          </div>
          {outputPath && (
            <p className="rounded-md border border-border-subtle bg-bg-raised px-3 py-2 font-mono text-xs text-fg-muted text-left break-all">
              {outputPath}
            </p>
          )}
          <div className="flex gap-2 justify-center">
            <Button variant="secondary" onClick={onReset}>
              New run
            </Button>
            {outputPath && <OpenInFolderButton path={outputPath} />}
          </div>
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="w-full max-w-md panel p-6 space-y-4 border-danger/40">
          <div>
            <h2 className="text-sm font-bold text-danger">Run failed</h2>
            <p className="mt-1 text-xs text-fg-dim leading-relaxed break-all">
              {errorMessage ?? "Unknown error."}
            </p>
          </div>
          <div className="flex justify-end">
            <Button variant="primary" onClick={onReset}>
              Reset
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

function OpenInFolderButton({ path }: { path: string }) {
  const openParent = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-shell");
      // Open the parent directory in Explorer / Finder. Plugin-shell
      // doesn't expose a cross-platform "reveal in folder", so we open
      // the directory containing the PDF instead.
      const parent = path.replace(/[/\\][^/\\]+$/, "");
      await open(parent);
    } catch {
      // Outside Tauri (dev browser) — silently no-op.
    }
  };
  return (
    <Button variant="secondary" onClick={openParent}>
      <FolderOpen className="h-4 w-4" />
      Show in folder
    </Button>
  );
}
