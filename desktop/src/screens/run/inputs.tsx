import { PlayCircle } from "lucide-react";
import { useState } from "react";

import { FilePicker } from "@/components/file-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type RunInputs = {
  master?: string;
  resume?: string;
  facts?: string;
  job: string;
  output?: string;
  style?: string;
  no_enrich: boolean;
  no_approve: boolean;
  max_iter?: number;
};

type Props = {
  onSubmit: (inputs: RunInputs) => void;
  disabled?: boolean;
};

/**
 * Pre-flight inputs for the Run flow. Layout: a single centered card
 * with the three required pickers (master | resume | job) up front,
 * advanced opts collapsed into a footer row. Submit is disabled until
 * a master-or-resume + job is selected.
 */
export function RunInputs({ onSubmit, disabled }: Props) {
  const [master, setMaster] = useState("");
  const [resume, setResume] = useState("");
  const [facts, setFacts] = useState("");
  const [job, setJob] = useState("");
  const [output, setOutput] = useState("");
  const [style, setStyle] = useState("");
  const [noEnrich, setNoEnrich] = useState(false);
  const [noApprove, setNoApprove] = useState(false);
  const [maxIter, setMaxIter] = useState<string>("");

  const canSubmit = (!!master || !!resume) && !!job && !disabled;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({
      master: master || undefined,
      resume: master ? undefined : resume || undefined,
      facts: facts || undefined,
      job,
      output: output || undefined,
      style: style || undefined,
      no_enrich: noEnrich,
      no_approve: noApprove,
      max_iter: maxIter ? Number(maxIter) : undefined,
    });
  };

  return (
    <div className="mx-auto max-w-2xl p-6">
      <header className="mb-6">
        <h1 className="text-sm font-bold text-fg">Run</h1>
        <p className="mt-1 text-xs text-fg-dim leading-relaxed">
          Full pipeline: load → score → tailor → optional enrich → optional
          approval loop → finalize. Three required inputs; advanced flags
          mirror the CLI.
        </p>
      </header>

      <div className="space-y-4 panel p-4">
        <FieldRow label="Master YAML">
          <FilePicker
            value={master}
            onChange={(v) => {
              setMaster(v);
              if (v) setResume("");
            }}
            placeholder="data/master_resume.yaml"
            filters={[{ name: "YAML", extensions: ["yaml", "yml"] }]}
          />
        </FieldRow>

        <FieldRow label="…or Resume PDF (legacy)">
          <FilePicker
            value={resume}
            onChange={(v) => {
              setResume(v);
              if (v) setMaster("");
            }}
            placeholder="resume.pdf"
            filters={[{ name: "PDF", extensions: ["pdf"] }]}
          />
        </FieldRow>

        <FieldRow label="Job Description" required>
          <FilePicker
            value={job}
            onChange={setJob}
            placeholder="input/job.txt"
            filters={[{ name: "Text", extensions: ["txt", "md"] }]}
          />
        </FieldRow>

        <FieldRow label="Facts Bank YAML" optional>
          <FilePicker
            value={facts}
            onChange={setFacts}
            placeholder="(optional — defaults to data/facts_bank.yaml if present)"
            filters={[{ name: "YAML", extensions: ["yaml", "yml"] }]}
          />
        </FieldRow>

        <FieldRow label="Style Template" optional>
          <FilePicker
            value={style}
            onChange={setStyle}
            placeholder="(optional — overrides RESUME_STYLE_PATH)"
            filters={[{ name: "YAML", extensions: ["yaml", "yml"] }]}
          />
        </FieldRow>
      </div>

      <details className="panel mt-4 group">
        <summary className="cursor-pointer px-4 py-2 text-xs uppercase tracking-wider text-fg-muted">
          Advanced
        </summary>
        <div className="px-4 pb-4 space-y-3">
          <FieldRow label="Output parent" optional>
            <Input
              value={output}
              onChange={(e) => setOutput(e.target.value)}
              placeholder="(default: data/applications/)"
            />
          </FieldRow>
          <FieldRow label="Max approval iterations" optional>
            <Input
              type="number"
              min={1}
              value={maxIter}
              onChange={(e) => setMaxIter(e.target.value)}
              placeholder="(default: RESUME_MAX_ITERATIONS)"
            />
          </FieldRow>
          <CheckboxRow
            checked={noEnrich}
            onChange={setNoEnrich}
            label="Skip auto-enrich"
            hint="Don't offer the interview even if the first tailor is thin."
          />
          <CheckboxRow
            checked={noApprove}
            onChange={setNoApprove}
            label="Skip approval loop"
            hint="Render the first tailored version directly. Headless mode."
          />
        </div>
      </details>

      <div className="mt-6 flex justify-end">
        <Button
          variant="primary"
          size="lg"
          disabled={!canSubmit}
          onClick={submit}
        >
          <PlayCircle className="h-4 w-4" />
          Start run
        </Button>
      </div>
    </div>
  );
}

function FieldRow({
  label,
  required,
  optional,
  children,
}: {
  label: string;
  required?: boolean;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[180px_1fr] items-center gap-3">
      <Label>
        {label}
        {required && <span className="ml-1 text-accent normal-case">*</span>}
        {optional && (
          <span className="ml-1 text-fg-faint normal-case">(optional)</span>
        )}
      </Label>
      <div>{children}</div>
    </div>
  );
}

function CheckboxRow({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2 text-sm text-fg">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-border accent-accent"
      />
      <div>
        <span>{label}</span>
        {hint && (
          <p className="mt-0.5 text-xs text-fg-dim leading-relaxed">{hint}</p>
        )}
      </div>
    </label>
  );
}
