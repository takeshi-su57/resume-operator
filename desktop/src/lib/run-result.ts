/**
 * Interpret a serialized `ResumeOptimizerState` result for status display.
 *
 * `task.result` (and `useRunSession.result`) carries the full pipeline
 * state, including `errors` from nodes that recorded a problem without
 * crashing. A run can therefore reach `status === "completed"` while
 * having produced no PDF — typical case: `optimize_content` rejected
 * every fabricated item, leaving zero tailored items, and `generate_pdf`
 * skipped. The status pill alone hides that.
 *
 * `outputPath` is set in the initial state regardless of success, so it
 * is not a reliable signal — `pdfGenerated` checks the actual presence
 * of tailored items, which is the necessary precondition for the PDF.
 */

export type RunResultStatus = {
  errors: string[];
  outputPath: string | null;
  tailoredItemCount: number;
  pdfGenerated: boolean;
  hasErrors: boolean;
};

export function interpretRunResult(
  result: Record<string, unknown> | null,
): RunResultStatus {
  const errors = stringArray(result?.errors);
  const outputPath =
    typeof result?.output_path === "string" ? result.output_path : null;
  const tailoredItemCount = countItems(result?.tailored_resume);
  return {
    errors,
    outputPath,
    tailoredItemCount,
    pdfGenerated: tailoredItemCount > 0 && errors.every(notFatalForPdf),
    hasErrors: errors.length > 0,
  };
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === "string");
}

function countItems(tailored: unknown): number {
  if (!tailored || typeof tailored !== "object") return 0;
  const items = (tailored as { items?: unknown }).items;
  return Array.isArray(items) ? items.length : 0;
}

function notFatalForPdf(err: string): boolean {
  return !err.includes("generate_pdf: skipping") && !err.includes("PDF generation failed");
}
