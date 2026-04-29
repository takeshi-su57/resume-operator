import { Loader2 } from "lucide-react";
import { useState } from "react";

import { FilePicker } from "@/components/file-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useExtractStyle, type StyleTemplate } from "@/lib/api";

/**
 * Extract Style — wraps the CLI `extract-style` command (#72).
 * .docx in → StyleTemplate JSON shown for inspection, optionally
 * written to a chosen output YAML path.
 */
export function ExtractStyleScreen() {
  const [source, setSource] = useState("");
  const [output, setOutput] = useState("");
  const extract = useExtractStyle();

  const submit = () => {
    if (!source) return;
    extract.mutate({ source, output: output || undefined });
  };

  return (
    <div className="grid h-full grid-cols-[320px_1fr]">
      <aside className="space-y-4 border-r border-border bg-bg-panel p-4 overflow-y-auto">
        <header>
          <h1 className="text-sm font-bold text-fg">Extract Style</h1>
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            Derive a StyleTemplate YAML from a reference .docx — fonts,
            margins, sizes. Apply via <span className="font-mono text-fg">
              run --style
            </span>.
          </p>
        </header>
        <div className="space-y-2">
          <Label>Source .docx</Label>
          <FilePicker
            value={source}
            onChange={setSource}
            placeholder="reference-resume.docx"
            filters={[{ name: "Word", extensions: ["docx"] }]}
          />
        </div>
        <div className="space-y-2">
          <Label>
            Output YAML
            <span className="ml-1 text-fg-faint normal-case">(optional)</span>
          </Label>
          <Input
            value={output}
            onChange={(e) => setOutput(e.target.value)}
            placeholder="(leave empty to inspect only)"
          />
        </div>
        <Button
          variant="primary"
          size="lg"
          className="w-full"
          disabled={!source || extract.isPending}
          onClick={submit}
        >
          {extract.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Extracting…
            </>
          ) : (
            "Extract"
          )}
        </Button>
        {extract.isError && (
          <p className="text-xs text-danger">{extract.error?.message}</p>
        )}
      </aside>

      <section className="overflow-y-auto p-6">
        {extract.data ? (
          <StylePreview
            template={extract.data.style}
            writtenTo={extract.data.written_to}
          />
        ) : (
          <EmptyState pending={extract.isPending} />
        )}
      </section>
    </div>
  );
}

function StylePreview({
  template,
  writtenTo,
}: {
  template: StyleTemplate;
  writtenTo: string | null;
}) {
  return (
    <div className="space-y-4 max-w-2xl">
      {writtenTo && (
        <p className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-xs text-success font-mono break-all">
          Wrote {writtenTo}
        </p>
      )}
      <section className="panel p-4 space-y-3">
        <h3 className="text-xs uppercase tracking-wider text-fg-muted">
          Style Template
        </h3>
        <Field label="Font family" value={template.font_family} />
        <Field label="Margins (top)" value={`${template.margins.top}in`} />
        <Field label="Margins (bottom)" value={`${template.margins.bottom}in`} />
        <Field label="Margins (side)" value={`${template.margins.side}in`} />
        <Field label="Name size" value={`${template.name_style.size}pt`} />
        <Field label="Section size" value={`${template.section.size}pt`} />
        <Field label="Body size" value={`${template.body.size}pt`} />
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[140px_1fr] items-baseline gap-3">
      <span className="text-xs uppercase tracking-wider text-fg-muted">
        {label}
      </span>
      <span className="text-sm text-fg font-mono">{value}</span>
    </div>
  );
}

function EmptyState({ pending }: { pending: boolean }) {
  if (pending) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-fg-dim">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Reading .docx styles…
      </div>
    );
  }
  return (
    <div className="flex h-full items-center justify-center text-sm text-fg-faint">
      <p>Pick a .docx to extract its style template.</p>
    </div>
  );
}
