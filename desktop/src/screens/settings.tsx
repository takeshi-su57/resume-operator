import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useSettings,
  useUpdateSettings,
  type SettingsPayload,
  type SettingsUpdate,
} from "@/lib/api";

const PROVIDERS = ["openai", "anthropic", "google", "openrouter"];

const KEY_FIELDS: { id: keyof SettingsPayload; label: string; provider: string }[] = [
  { id: "openai_api_key", label: "OpenAI API key", provider: "openai" },
  { id: "anthropic_api_key", label: "Anthropic API key", provider: "anthropic" },
  { id: "google_api_key", label: "Google API key", provider: "google" },
  { id: "openrouter_api_key", label: "OpenRouter API key", provider: "openrouter" },
];

const ATS_WEIGHTS: { id: keyof SettingsPayload; label: string }[] = [
  { id: "ats_weight_hard", label: "Hard skills" },
  { id: "ats_weight_soft", label: "Soft skills" },
  { id: "ats_weight_structural", label: "Structural" },
  { id: "ats_weight_title", label: "Title match" },
  { id: "ats_weight_measurable", label: "Measurable" },
  { id: "ats_weight_tone", label: "Tone" },
];

/**
 * Settings screen — surfaces every env var from `config.py`. Reads
 * arrive with API keys masked (`sk-p…7890`); when the user types into a
 * key field, it's treated as a brand new value and written through.
 *
 * Validates server-side via the route's pydantic model — no client-side
 * weight-sum check (the server caps each weight at [0, 1]; the user can
 * tune freely).
 */
export function SettingsScreen() {
  const { data, isLoading, isError, error, refetch } = useSettings();
  const update = useUpdateSettings({
    onSuccess: () => refetch(),
  });

  const [draft, setDraft] = useState<SettingsUpdate>({});
  const [keyEdits, setKeyEdits] = useState<Record<string, string>>({});

  // Reset the draft whenever the source-of-truth payload changes.
  useEffect(() => {
    setDraft({});
    setKeyEdits({});
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-fg-dim">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading settings…
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-sm text-danger">
        <p>Failed to load settings.</p>
        <p className="mt-1 text-xs text-fg-dim">{(error as Error)?.message}</p>
        <Button className="mt-3" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const merged: SettingsPayload = { ...data, ...(draft as SettingsPayload) };
  const dirty =
    Object.keys(draft).length > 0 || Object.keys(keyEdits).length > 0;

  const setField = <K extends keyof SettingsPayload>(
    key: K,
    value: SettingsPayload[K],
  ) => setDraft((prev) => ({ ...prev, [key]: value }));

  const submit = () => {
    if (!dirty) return;
    const payload: SettingsUpdate = { ...draft, ...keyEdits };
    update.mutate(payload);
  };

  const reset = () => {
    setDraft({});
    setKeyEdits({});
  };

  return (
    <div className="mx-auto max-w-3xl p-6">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-sm font-bold text-fg">Settings</h1>
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            Persists to <span className="font-mono text-fg">.env</span> in the
            project root. API keys arrive masked — type a new value to replace.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={!dirty} onClick={reset}>
            Reset
          </Button>
          <Button
            variant="primary"
            disabled={!dirty || update.isPending}
            onClick={submit}
          >
            {update.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              "Save"
            )}
          </Button>
        </div>
      </header>

      {update.isError && (
        <p className="mb-4 text-xs text-danger">
          {update.error?.message || "Save failed."}
        </p>
      )}

      <div className="space-y-6">
        <Section title="LLM Provider">
          <Field label="Provider">
            <Select
              value={merged.llm_provider}
              onValueChange={(v) => setField("llm_provider", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDERS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Model">
            <Input
              value={merged.llm_model}
              onChange={(e) => setField("llm_model", e.target.value)}
              placeholder="gpt-4o, claude-sonnet-4-6, gemini-2.0-flash, …"
            />
          </Field>
        </Section>

        <Section title="API Keys">
          {KEY_FIELDS.map((f) => (
            <Field key={f.id} label={f.label}>
              <Input
                type="password"
                value={keyEdits[f.id] ?? ""}
                onChange={(e) =>
                  setKeyEdits((prev) => ({ ...prev, [f.id]: e.target.value }))
                }
                placeholder={
                  (data[f.id] as string) || "(empty — paste key to set)"
                }
              />
            </Field>
          ))}
        </Section>

        <Section title="Behavior">
          <Field label="Log level">
            <Select
              value={merged.log_level}
              onValueChange={(v) => setField("log_level", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["DEBUG", "INFO", "WARNING", "ERROR"].map((l) => (
                  <SelectItem key={l} value={l}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="ATS skip threshold">
            <Input
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={merged.ats_skip_threshold}
              onChange={(e) =>
                setField("ats_skip_threshold", Number(e.target.value))
              }
            />
          </Field>
          <Field label="Enrich threshold">
            <Input
              type="number"
              min={0}
              value={merged.enrich_threshold}
              onChange={(e) =>
                setField("enrich_threshold", Number(e.target.value))
              }
            />
          </Field>
          <Field label="Max approval iterations">
            <Input
              type="number"
              min={1}
              value={merged.resume_max_iterations}
              onChange={(e) =>
                setField("resume_max_iterations", Number(e.target.value))
              }
            />
          </Field>
          <Field label="Resume style YAML path">
            <Input
              value={merged.resume_style_path}
              onChange={(e) => setField("resume_style_path", e.target.value)}
              placeholder="(empty — falls back to default style)"
            />
          </Field>
        </Section>

        <Section
          title="ATS Composite Weights"
          subtitle="Six dimensions; tune per JD category. Server caps each at [0, 1]."
        >
          <div className="grid grid-cols-2 gap-4">
            {ATS_WEIGHTS.map((w) => (
              <Field key={w.id} label={w.label}>
                <Input
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={merged[w.id] as number}
                  onChange={(e) =>
                    setField(
                      w.id as keyof SettingsPayload,
                      Number(e.target.value) as never,
                    )
                  }
                />
              </Field>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel p-4">
      <h2 className="text-xs uppercase tracking-wider text-fg-muted">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-1 text-xs text-fg-dim leading-relaxed">{subtitle}</p>
      )}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[180px_1fr] items-center gap-3">
      <Label>{label}</Label>
      <div>{children}</div>
    </div>
  );
}
