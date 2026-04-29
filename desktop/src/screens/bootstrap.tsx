import { Loader2, PlayCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { FilePicker } from "@/components/file-picker";
import { HistoryList } from "@/components/history-list";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ServerMessage } from "@/lib/events";
import { useFlowSocket } from "@/lib/ws";
import { useHistoryActions } from "@/state/history";

type Phase = "idle" | "starting" | "running" | "prompt" | "done" | "error";

type LogEntry = {
  kind: "panel" | "notice" | "status_start" | "status_end";
  message: string;
  title?: string;
  at: number;
};

type Pending =
  | { kind: "confirm"; message: string; default: boolean }
  | { kind: "choose"; message: string; choices: string[]; default: string }
  | { kind: "text"; message: string; default: string }
  | null;

/**
 * Bootstrap screen — wraps the CLI `bootstrap` command (#60, #70).
 * PDF in → master YAML out, with the senior-format interview running
 * over `/api/ws/bootstrap`.
 *
 * Simpler than the Run screen — no node timeline, no approval loop,
 * no enrichment. The activity flows linearly: pick PDF → start →
 * watch the parser run → answer headline / links / per-role tech /
 * skill grouping prompts → see the YAML write summary.
 */
export function BootstrapScreen() {
  const [resume, setResume] = useState("");
  const [output, setOutput] = useState("data/master_resume.yaml");
  const [skipInterview, setSkipInterview] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const { push: pushHistory } = useHistoryActions();

  const handleMessage = useCallback(
    (msg: ServerMessage) => {
      switch (msg.type) {
        case "status_start":
        case "status_end":
          setLogs((prev) => [
            ...prev,
            {
              kind: msg.type,
              message: msg.type === "status_start" ? msg.message : "",
              at: msg.at,
            },
          ]);
          return;
        case "panel":
        case "notice":
          setLogs((prev) => [
            ...prev,
            {
              kind: msg.type,
              message: msg.message,
              title: msg.type === "panel" ? msg.title : undefined,
              at: Date.now(),
            },
          ]);
          return;
        case "confirm":
          setPending({ kind: "confirm", message: msg.message, default: msg.default });
          setPhase("prompt");
          return;
        case "choose":
          setPending({
            kind: "choose",
            message: msg.message,
            choices: msg.choices,
            default: msg.default,
          });
          setPhase("prompt");
          return;
        case "text":
          setPending({ kind: "text", message: msg.message, default: msg.default });
          setPhase("prompt");
          return;
        case "done": {
          setResult(msg.result);
          setPhase("done");
          // Persist a history row so Bruno can revisit either path
          // later. The server normalizes `output_path` from the params,
          // so we trust whatever it echoes back over `resume` UI state.
          const outputPath =
            typeof msg.result?.output_path === "string"
              ? msg.result.output_path
              : output;
          if (resume && outputPath) {
            pushHistory("bootstrap", {
              source: resume,
              output: outputPath,
              at: Date.now(),
            });
          }
          return;
        }
        case "error":
          setErrorMsg(msg.message);
          setPhase("error");
          return;
        default:
          return;
      }
    },
    [resume, output, pushHistory],
  );

  const ws = useFlowSocket({ onMessage: handleMessage });

  // Send Start once the socket is open.
  const startedRef = useRef(false);
  useEffect(() => {
    if (ws.status === "open" && startedRef.current) {
      ws.send({
        type: "start",
        params: { resume, output, skip_interview: skipInterview },
      });
      startedRef.current = false;
      setPhase("running");
    }
  }, [ws.status, ws, resume, output, skipInterview]);

  const submit = () => {
    if (!resume) return;
    setLogs([]);
    setPending(null);
    setResult(null);
    setErrorMsg(null);
    startedRef.current = true;
    setPhase("starting");
    ws.connect("/api/ws/bootstrap");
  };

  const reset = () => {
    ws.disconnect();
    setPhase("idle");
    setLogs([]);
    setPending(null);
    setResult(null);
    setErrorMsg(null);
  };

  const reply = (value: string | boolean) => {
    ws.send({ type: "reply", value });
    setPending(null);
    setPhase("running");
  };

  return (
    <div className="grid h-full grid-cols-[320px_1fr]">
      <aside className="space-y-4 border-r border-border bg-bg-panel p-4 overflow-y-auto">
        <header>
          <h1 className="text-sm font-bold text-fg">Bootstrap</h1>
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            One-time: parse a resume PDF into a hand-editable
            <span className="font-mono text-fg"> master_resume.yaml</span>.
            Walks an interview to fill in headline, links, per-role tech,
            and skill groupings.
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
        <div className="space-y-2">
          <Label>Output YAML</Label>
          <FilePicker
            value={output}
            onChange={setOutput}
            placeholder="data/master_resume.yaml"
            mode="save-file"
            defaultName="master_resume.yaml"
            filters={[{ name: "YAML", extensions: ["yaml", "yml"] }]}
          />
        </div>
        <label className="flex cursor-pointer items-start gap-2 text-sm text-fg">
          <input
            type="checkbox"
            checked={skipInterview}
            onChange={(e) => setSkipInterview(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-border accent-accent"
          />
          <div>
            <span>Skip interview</span>
            <p className="mt-0.5 text-xs text-fg-dim leading-relaxed">
              Save the parsed YAML as-is, without prompting for senior-format
              fields.
            </p>
          </div>
        </label>
        <Button
          variant="primary"
          size="lg"
          className="w-full"
          disabled={!resume || phase === "running" || phase === "starting"}
          onClick={phase === "idle" || phase === "done" || phase === "error" ? submit : reset}
        >
          {phase === "running" || phase === "starting" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Running…
            </>
          ) : phase === "done" || phase === "error" ? (
            "Reset"
          ) : (
            <>
              <PlayCircle className="h-4 w-4" />
              Bootstrap
            </>
          )}
        </Button>
        <HistoryList
          page="bootstrap"
          title="Recent bootstraps"
          onPick={(entry) => {
            setResume(entry.source);
            setOutput(entry.output);
          }}
        />
      </aside>

      <section className="flex flex-col overflow-hidden">
        <ActivityLog logs={logs} className="flex-1" />
        {phase === "prompt" && pending && (
          <PromptPanel pending={pending} onReply={reply} />
        )}
        {phase === "done" && (
          <DonePanel result={result} />
        )}
        {phase === "error" && errorMsg && (
          <ErrorPanel message={errorMsg} />
        )}
      </section>
    </div>
  );
}

function ActivityLog({ logs, className }: { logs: LogEntry[]; className?: string }) {
  if (logs.length === 0) {
    return (
      <div className={`flex items-center justify-center text-sm text-fg-faint ${className}`}>
        Pick a resume PDF and click Bootstrap to begin.
      </div>
    );
  }
  return (
    <ul className={`space-y-2 overflow-y-auto p-6 ${className}`}>
      {logs.map((log, i) => (
        <li
          key={i}
          className={
            log.kind === "panel"
              ? "panel p-3 text-sm text-fg leading-relaxed"
              : "text-xs text-fg-muted"
          }
        >
          {log.title && (
            <p className="text-xs uppercase tracking-wider text-fg-muted mb-1">
              {log.title}
            </p>
          )}
          <p className="whitespace-pre-wrap">
            {log.message.replace(/\[\/?[^\]]+\]/g, "")}
          </p>
        </li>
      ))}
    </ul>
  );
}

function PromptPanel({
  pending,
  onReply,
}: {
  pending: Exclude<Pending, null>;
  onReply: (value: string | boolean) => void;
}) {
  const [text, setText] = useState(
    pending.kind === "text" ? pending.default : "",
  );
  return (
    <div className="border-t border-border bg-bg-panel p-4 space-y-3">
      <p className="text-sm text-fg leading-relaxed">
        {pending.message.replace(/\[\/?[^\]]+\]/g, "")}
      </p>
      {pending.kind === "confirm" && (
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => onReply(true)}>
            Yes
          </Button>
          <Button variant="secondary" onClick={() => onReply(false)}>
            No
          </Button>
        </div>
      )}
      {pending.kind === "choose" && (
        <div className="flex flex-wrap gap-2">
          {pending.choices.map((c) => (
            <Button key={c} variant="secondary" onClick={() => onReply(c)}>
              {c}
            </Button>
          ))}
        </div>
      )}
      {pending.kind === "text" && (
        <div className="flex gap-2">
          <Input
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={pending.default}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onReply(text);
              }
            }}
          />
          <Button variant="primary" onClick={() => onReply(text)}>
            Send
          </Button>
        </div>
      )}
    </div>
  );
}

function DonePanel({ result }: { result: Record<string, unknown> | null }) {
  const path = typeof result?.output_path === "string" ? result.output_path : null;
  return (
    <div className="border-t border-success/40 bg-success/10 p-4 space-y-2">
      <p className="text-sm font-bold text-success">Bootstrap complete</p>
      {path && (
        <p className="text-xs text-fg-muted font-mono break-all">
          Wrote {path}
        </p>
      )}
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="border-t border-danger/40 bg-danger/10 p-4">
      <p className="text-sm font-bold text-danger">Bootstrap failed</p>
      <p className="mt-1 text-xs text-fg-dim leading-relaxed break-all">
        {message}
      </p>
    </div>
  );
}
