import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { RevealInFolderButton } from "@/components/reveal-in-folder-button";
import { Button } from "@/components/ui/button";
import { interpretRunResult } from "@/lib/run-result";
import { useRunSession } from "@/state/run-session";

/**
 * Center pane terminal states — `done` and `error`.
 *
 * `done` splits into three branches:
 *
 *   - **Clean success** — PDF generated, no errors. Green check, output
 *     path, and "Show in folder".
 *   - **Completed with warnings** — PDF generated, but some node
 *     recorded a non-fatal error (e.g. fabrication-guard rejected a few
 *     items). Yellow warning, errors listed, output path still
 *     surfaced because the user has something to inspect.
 *   - **Completed without PDF** — `optimize_content` rejected every
 *     item or `generate_pdf` skipped. Yellow warning, errors listed,
 *     no folder button (the planned `output_path` doesn't actually
 *     exist on disk).
 *
 * The third branch is the case Bruno hit when an LLM emitted a single
 * fabricated `source_id` and the run still reported `completed`.
 */
export function StatusPane({ onReset }: { onReset: () => void }) {
  const phase = useRunSession((s) => s.phase);
  const result = useRunSession((s) => s.result);
  const errorMessage = useRunSession((s) => s.errorMessage);

  if (phase === "done") {
    const status = interpretRunResult(result);
    if (status.pdfGenerated && !status.hasErrors) {
      return <CleanSuccessPanel outputPath={status.outputPath} onReset={onReset} />;
    }
    return (
      <CompletedWithIssuesPanel
        outputPath={status.pdfGenerated ? status.outputPath : null}
        errors={status.errors}
        tailoredItemCount={status.tailoredItemCount}
        onReset={onReset}
      />
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

function CleanSuccessPanel({
  outputPath,
  onReset,
}: {
  outputPath: string | null;
  onReset: () => void;
}) {
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
          {outputPath && (
            <RevealInFolderButton
              path={outputPath}
              label="Show in folder"
              variant="secondary"
              size="md"
            />
          )}
        </div>
      </div>
    </div>
  );
}

function CompletedWithIssuesPanel({
  outputPath,
  errors,
  tailoredItemCount,
  onReset,
}: {
  outputPath: string | null;
  errors: string[];
  tailoredItemCount: number;
  onReset: () => void;
}) {
  const noPdf = outputPath == null;
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="w-full max-w-lg panel p-6 space-y-4 border-warn/40">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warn/15">
            <AlertTriangle className="h-5 w-5 text-warn" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-fg">
              {noPdf ? "Completed — no PDF generated" : "Completed with warnings"}
            </h2>
            <p className="mt-1 text-xs text-fg-dim leading-relaxed">
              {noPdf
                ? `The pipeline finished but produced ${tailoredItemCount} tailored item${tailoredItemCount === 1 ? "" : "s"}, so the PDF was skipped. Re-running often resolves transient LLM hiccups.`
                : "The pipeline produced a PDF, but some nodes recorded issues worth checking before sending the resume out."}
            </p>
          </div>
        </div>

        {errors.length > 0 && (
          <div className="rounded-md border border-border-subtle bg-bg-raised p-3 text-left">
            <p className="mb-1.5 text-[0.6875rem] font-semibold uppercase tracking-wide text-fg-faint">
              Recorded issues ({errors.length})
            </p>
            <ul className="space-y-1 font-mono text-xs text-fg-muted break-all">
              {errors.map((err, idx) => (
                <li key={idx} className="leading-relaxed">
                  · {err}
                </li>
              ))}
            </ul>
          </div>
        )}

        {outputPath && (
          <p className="rounded-md border border-border-subtle bg-bg-raised px-3 py-2 font-mono text-xs text-fg-muted text-left break-all">
            {outputPath}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onReset}>
            New run
          </Button>
          {outputPath && (
            <RevealInFolderButton
              path={outputPath}
              label="Show in folder"
              variant="secondary"
              size="md"
            />
          )}
        </div>
      </div>
    </div>
  );
}
