import {
  ChevronRight,
  FileSearch,
  Gauge,
  PlayCircle,
  Settings,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useHealth } from "@/lib/api";
import { cn } from "@/lib/cn";

type Tile = {
  to: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  primary?: boolean;
};

const TILES: Tile[] = [
  {
    to: "/run",
    label: "Tailor a resume",
    description:
      "Full pipeline — load → score → tailor → optional enrich → optional approval loop → finalize.",
    icon: PlayCircle,
    primary: true,
  },
  {
    to: "/score",
    label: "Score against a JD",
    description:
      "Multi-dimensional ATS report (#81). No tailoring, no PDF write — read-only inspection.",
    icon: Gauge,
  },
  {
    to: "/bootstrap",
    label: "Bootstrap from PDF",
    description:
      "One-time: parse a resume PDF into a hand-editable master_resume.yaml.",
    icon: Sparkles,
  },
  {
    to: "/parse",
    label: "Parse PDF",
    description:
      "Inspect what the LLM extracts from a resume PDF — fields, counts, raw text.",
    icon: FileSearch,
  },
  {
    to: "/style",
    label: "Extract style",
    description:
      "Derive a StyleTemplate YAML from a reference .docx (#72). Apply via run --style.",
    icon: Wrench,
  },
  {
    to: "/settings",
    label: "Settings",
    description: "LLM provider + keys, ATS weights, behavior thresholds.",
    icon: Settings,
  },
];

/**
 * Home / dashboard. Quick-action tiles for every screen plus an
 * engine status hero. The "recent applications" feed lives on the
 * roadmap but isn't shipped here — it would need either a fs-listing
 * server route or `@tauri-apps/plugin-fs`, both of which expand the
 * Phase 5 scope without unblocking anything. Left as a follow-up.
 */
export function HomeScreen() {
  const { data: health, isError } = useHealth();
  const navigate = useNavigate();
  const ok = !!health && !isError;

  return (
    // App shell's <main> is `overflow-hidden` — child needs `h-full`
    // for `overflow-y-auto` to engage (otherwise it sizes to content
    // and gets clipped by main).
    <div className="h-full overflow-y-auto p-8 max-w-5xl mx-auto w-full">
      <header className="mb-8">
        <h1 className="text-lg font-bold text-fg">resume-operator</h1>
        <p className="mt-1 text-sm text-fg-dim">
          Local AI agent that tailors your resume to any job description.
        </p>
        <div
          className={cn(
            "mt-3 inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs",
            ok
              ? "border-success/30 bg-success/5 text-success"
              : "border-danger/30 bg-danger/5 text-danger",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              ok ? "bg-success" : "bg-danger",
            )}
          />
          {ok ? (
            <span>
              Engine online · {health!.llm_provider} / {health!.llm_model}
            </span>
          ) : (
            <span>Engine offline — start the sidecar with <span className="font-mono">uv run resume-operator-server</span></span>
          )}
        </div>
      </header>

      <ul className="grid grid-cols-2 gap-3">
        {TILES.map((tile) => (
          <Tile key={tile.to} tile={tile} onClick={() => navigate(tile.to)} />
        ))}
      </ul>
    </div>
  );
}

function Tile({ tile, onClick }: { tile: Tile; onClick: () => void }) {
  const Icon = tile.icon;
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "panel w-full p-4 text-left transition-colors group focus-ring",
          tile.primary
            ? "border-accent/40 hover:border-accent/60 hover:bg-bg-raised"
            : "hover:border-border-strong hover:bg-bg-raised",
        )}
      >
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "rounded-md border p-2",
              tile.primary
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-border bg-bg-raised text-fg-muted",
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-bold text-fg flex items-center gap-1">
              {tile.label}
              <ChevronRight className="h-3.5 w-3.5 text-fg-faint group-hover:text-fg-muted transition-colors" />
            </h3>
            <p className="mt-1 text-xs text-fg-dim leading-relaxed">
              {tile.description}
            </p>
          </div>
        </div>
      </button>
    </li>
  );
}
