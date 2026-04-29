import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { FilePicker } from "@/components/file-picker";
import { YamlPreviewDialog } from "@/components/yaml-preview-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useTaskStore } from "@/state/task-store";

/**
 * `/score/new` — pre-flight inputs for a Score task. Master YAML is
 * preferred; a legacy resume PDF is the fallback for users who haven't
 * bootstrapped a master yet. On submit, registers the task and
 * navigates straight to its detail view.
 */
export function ScoreNewScreen() {
  const [master, setMaster] = useState("");
  const [resume, setResume] = useState("");
  const [job, setJob] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startScore = useTaskStore((s) => s.startScore);
  const navigate = useNavigate();

  const canSubmit = (!!master || !!resume) && !!job && !submitting;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const taskId = await startScore({
        master: master || undefined,
        resume: master ? undefined : resume || undefined,
        job,
      });
      navigate(`/score/${taskId}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start score");
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto p-6">
      <header className="mb-6">
        <h1 className="text-sm font-bold text-fg">New score</h1>
        <p className="mt-1 text-xs text-fg-dim leading-relaxed">
          Multi-dimensional ATS report against a job description. Doesn't
          tailor or write a PDF — read-only inspection only.
        </p>
      </header>

      <div className="space-y-4 panel p-4">
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

        <div className="flex items-center justify-end gap-2 pt-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/score")}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="lg"
            onClick={submit}
            disabled={!canSubmit}
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting…
              </>
            ) : (
              "Score"
            )}
          </Button>
        </div>

        {error && (
          <p className="text-xs text-danger">{error}</p>
        )}
      </div>
    </div>
  );
}
