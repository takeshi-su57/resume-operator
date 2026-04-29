import { Loader2 } from "lucide-react";
import { useState } from "react";

import { FilePicker } from "@/components/file-picker";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useParseResume, type ResumeData } from "@/lib/api";

/**
 * Parse Resume — wraps the CLI `parse-resume` command. PDF in,
 * read-only inspection of the extracted fields out. No tailoring,
 * no PDF writing.
 */
export function ParseResumeScreen() {
  const [resume, setResume] = useState("");
  const parse = useParseResume();

  const submit = () => {
    if (!resume) return;
    parse.mutate({ resume });
  };

  return (
    <div className="grid h-full grid-cols-[320px_1fr]">
      <aside className="space-y-4 border-r border-border bg-bg-panel p-4 overflow-y-auto">
        <header>
          <h1 className="text-sm font-bold text-fg">Parse Resume</h1>
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            Inspect what the LLM extracts from a resume PDF. No tailoring,
            no PDF write — read-only.
          </p>
        </header>
        <div className="space-y-2">
          <Label>Resume PDF</Label>
          <FilePicker
            value={resume}
            onChange={setResume}
            placeholder="resume.pdf"
            filters={[{ name: "PDF", extensions: ["pdf"] }]}
          />
        </div>
        <Button
          variant="primary"
          size="lg"
          className="w-full"
          disabled={!resume || parse.isPending}
          onClick={submit}
        >
          {parse.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Parsing…
            </>
          ) : (
            "Parse"
          )}
        </Button>
        {parse.isError && (
          <p className="text-xs text-danger">{parse.error?.message}</p>
        )}
      </aside>

      <section className="overflow-y-auto p-6">
        {parse.data ? (
          <ResumeFields data={parse.data.resume} />
        ) : (
          <EmptyState pending={parse.isPending} />
        )}
      </section>
    </div>
  );
}

function ResumeFields({ data }: { data: ResumeData }) {
  return (
    <div className="space-y-4 max-w-2xl">
      <section className="panel p-4 space-y-2">
        <Field label="Name" value={data.name} />
        <Field label="Email" value={data.email} />
        <Field label="Phone" value={data.phone} />
      </section>
      {data.summary && (
        <section className="panel p-4">
          <h3 className="text-xs uppercase tracking-wider text-fg-muted mb-2">
            Summary
          </h3>
          <p className="text-sm text-fg leading-relaxed">{data.summary}</p>
        </section>
      )}
      {data.skills.length > 0 && (
        <section className="panel p-4">
          <h3 className="text-xs uppercase tracking-wider text-fg-muted mb-2">
            Skills ({data.skills.length})
          </h3>
          <ul className="flex flex-wrap gap-1.5">
            {data.skills.map((s) => (
              <li
                key={s}
                className="rounded-sm border border-border bg-bg-raised px-1.5 py-0.5 text-xs text-fg-muted"
              >
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="panel p-4">
        <h3 className="text-xs uppercase tracking-wider text-fg-muted mb-2">
          Counts
        </h3>
        <dl className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Experience" value={data.experience.length} />
          <Stat label="Education" value={data.education.length} />
          <Stat label="Certifications" value={data.certifications.length} />
        </dl>
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[100px_1fr] items-baseline gap-3">
      <span className="text-xs uppercase tracking-wider text-fg-muted">
        {label}
      </span>
      <span className="text-sm text-fg font-mono break-all">
        {value || <span className="text-fg-faint">—</span>}
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-fg-muted">{label}</dt>
      <dd className="mt-0.5 text-2xl font-bold tabular-nums text-fg">{value}</dd>
    </div>
  );
}

function EmptyState({ pending }: { pending: boolean }) {
  if (pending) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-fg-dim">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Running LLM extraction…
      </div>
    );
  }
  return (
    <div className="flex h-full items-center justify-center text-sm text-fg-faint">
      <p>Pick a resume PDF to inspect its parsed fields.</p>
    </div>
  );
}
