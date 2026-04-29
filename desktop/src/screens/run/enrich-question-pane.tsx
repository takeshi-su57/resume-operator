import { ChevronRight, Loader2, SkipForward, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useRunSession } from "@/state/run-session";

type Props = {
  onSubmit: (text: string) => void;
  onSkip: () => void;
  onQuit: () => void;
};

/**
 * Enrichment question card. Server has emitted `render_question`
 * followed by a `text` prompt waiting on the user's free-text
 * answer. The user types facts/metrics in the textarea and either:
 *   - submits → server runs `polish_answer` → `render_polished`
 *   - skips → server moves to the next question
 *   - quits → ends the enrichment session
 *
 * The "skip" / "quit" actions submit the literal strings the server
 * understands (it short-circuits on those values inside
 * `tools.enrich.run_interactive_session`).
 */
export function EnrichQuestionPane({ onSubmit, onSkip, onQuit }: Props) {
  const question = useRunSession((s) => s.currentQuestion);
  const index = useRunSession((s) => s.questionIndex);
  const total = useRunSession((s) => s.questionTotal);

  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Reset the textarea each time a new question lands.
  useEffect(() => {
    setText("");
    ref.current?.focus();
  }, [question]);

  if (!question) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-fg-dim">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Generating questions…
      </div>
    );
  }

  const submit = () => {
    if (!text.trim()) return;
    onSubmit(text);
  };

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-border px-6 py-3">
        <div className="flex items-baseline gap-2">
          <p className="text-xs uppercase tracking-wider text-fg-muted">
            Enrichment · question {index} / {total}
          </p>
          {question.area && (
            <span className="rounded-sm border border-border bg-bg-raised px-1.5 py-0.5 font-mono text-xs text-fg-dim">
              {question.area}
            </span>
          )}
        </div>
        <h3 className="mt-1 text-sm font-bold text-fg leading-relaxed">
          {question.question}
        </h3>
        {question.why && (
          <p className="mt-1 text-xs text-fg-dim leading-relaxed">
            <span className="text-fg-faint">why:</span> {question.why}
          </p>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <p className="mb-2 text-xs text-fg-dim leading-relaxed">
          Answer with facts and metrics — e.g. <span className="text-fg-muted">
            "I built 50+ endpoints serving 2M requests/day"
          </span>. Don't type instructions ("make it professional"); the LLM
          polishes wording in the next step.
        </p>
        <textarea
          ref={ref}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type the facts here…"
          className="input-base min-h-[180px] resize-none font-mono leading-relaxed"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              submit();
            }
          }}
        />
      </div>

      <div
        className="border-t border-border px-6 py-2 flex items-center gap-2"
        data-no-select
      >
        <Button
          variant="primary"
          onClick={submit}
          disabled={!text.trim()}
          title="Polish (Ctrl+Enter)"
        >
          <ChevronRight className="h-4 w-4" />
          Polish
          <span className="kbd ml-1">Ctrl</span>
          <span className="kbd">⏎</span>
        </Button>
        <Button variant="secondary" onClick={onSkip} title="Skip this question">
          <SkipForward className="h-4 w-4" />
          Skip
        </Button>
        <div className="ml-auto">
          <Button variant="ghost" onClick={onQuit} title="End session">
            <X className="h-4 w-4" />
            Quit
          </Button>
        </div>
      </div>
    </div>
  );
}
