import { Loader2 } from "lucide-react";
import { useState } from "react";

import { AtsReport } from "@/components/ats-report";
import { FilePicker } from "@/components/file-picker";
import { ScoreProgress } from "@/components/score-progress";
import { YamlPreviewDialog } from "@/components/yaml-preview-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useScore } from "@/lib/api";

/**
 * Score screen — wraps the CLI `score` command. Picks a master YAML
 * (preferred) or legacy resume PDF + a job description text file, hits
 * `POST /api/score`, renders the multi-dim ATSReport on the right.
 *
 * Two-pane layout: inputs on the left (compact form), report on the
 * right. The report scrolls independently so a long hard-skill table
 * doesn't push the inputs off-screen.
 */
export function ScoreScreen() {
  const [master, setMaster] = useState("");
  const [resume, setResume] = useState("");
  const [job, setJob] = useState("");
  const score = useScore();

  const canSubmit = (!!master || !!resume) && !!job && !score.isPending;

  const submit = () => {
    if (!canSubmit) return;
    score.mutate({
      master: master || undefined,
      resume: master ? undefined : resume || undefined,
      job,
    });
  };

  return (
    <div className="grid h-full grid-cols-[320px_1fr]">
      <aside className="border-r border-border bg-bg-panel p-4 space-y-4 overflow-y-auto">
        <header>
          <h1 className="text-sm font-bold text-fg">Score</h1>
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            Multi-dimensional ATS report against a job description. Doesn't
            tailor or write a PDF — read-only inspection only.
          </p>
        </header>

        <div className="space-y-2">
          <Label htmlFor="master">Master YAML</Label>
          <div className="flex items-center gap-1.5">
            <FilePicker
              value={master}
              onChange={(v) => {
                setMaster(v);
                if (v) setResume("");
              }}
              placeholder="data/master_resume.yaml"
              filters={[{ name: "YAML", extensions: ["yaml", "yml"] }]}
              className="flex-1 min-w-0"
            />
            <YamlPreviewDialog path={master} iconOnly />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="resume">
            …or Resume PDF
            <span className="ml-1 text-fg-faint normal-case">(legacy)</span>
          </Label>
          <FilePicker
            value={resume}
            onChange={(v) => {
              setResume(v);
              if (v) setMaster("");
            }}
            placeholder="resume.pdf"
            filters={[{ name: "PDF", extensions: ["pdf"] }]}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="job">Job Description</Label>
          <FilePicker
            value={job}
            onChange={setJob}
            placeholder="input/job.txt"
            filters={[{ name: "Text", extensions: ["txt", "md"] }]}
          />
        </div>

        <div className="pt-2">
          <Button
            variant="primary"
            size="lg"
            onClick={submit}
            disabled={!canSubmit}
            className="w-full"
          >
            {score.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Scoring…
              </>
            ) : (
              "Score"
            )}
          </Button>
        </div>

        {score.isError && (
          <p className="text-xs text-danger">
            {score.error?.message || "Score failed."}
          </p>
        )}
      </aside>

      <section className="overflow-y-auto p-6">
        {score.isPending ? (
          // Mount with a fresh key per submit so the elapsed clock
          // restarts; without it React Query reuses the same
          // `score-progress` instance and the heuristic counter looks
          // wrong on subsequent runs.
          <ScoreProgress key={score.submittedAt} isPending />
        ) : score.data ? (
          <AtsReport
            report={score.data.ats_score}
            master={score.data.master_view}
          />
        ) : (
          <EmptyState />
        )}
      </section>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-sm text-fg-faint">
      <p>Pick a master YAML and a job description to score.</p>
      <p className="mt-1">
        Output: composite + per-dimension breakdown (#81).
      </p>
    </div>
  );
}
