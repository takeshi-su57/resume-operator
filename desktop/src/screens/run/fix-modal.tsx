import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Props = {
  open: boolean;
  onSubmit: (feedback: string) => void;
  onCancel: () => void;
  prompt?: string;
};

/**
 * Modal that opens after the user clicks "Fix…" on a proposal.
 * Captures free-text feedback the LLM uses to revise the proposal
 * (`tools.propose_changes.revise_proposal`). The Fix sub-loop is
 * unbounded server-side, so this modal can re-open indefinitely as
 * each revision arrives.
 */
export function FixModal({ open, onSubmit, onCancel, prompt }: Props) {
  const [text, setText] = useState("");
  const submit = () => {
    onSubmit(text);
    setText("");
  };
  const cancel = () => {
    setText("");
    onCancel();
  };
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && cancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 animate-fade-in" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
            "w-[min(640px,90vw)] panel p-6 animate-fade-in shadow-xl",
          )}
          onOpenAutoFocus={(e) => {
            // Focus the textarea, not the dialog frame.
            e.preventDefault();
            requestAnimationFrame(() => {
              const ta = document.querySelector<HTMLTextAreaElement>(
                "[data-fix-textarea]",
              );
              ta?.focus();
            });
          }}
        >
          <Dialog.Title className="text-sm font-bold text-fg">
            What should change?
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-xs text-fg-dim leading-relaxed">
            {prompt ??
              'Free text — e.g. "I never used K8s, only ECS". The LLM revises ' +
                "and brings the new version back to the same gate."}
          </Dialog.Description>

          <textarea
            data-fix-textarea
            className={cn(
              "mt-3 w-full h-32 input-base font-mono leading-relaxed resize-none",
            )}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type the correction here…"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submit();
              }
              if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
            }}
          />

          <div className="mt-4 flex items-center justify-between">
            <p className="text-xs text-fg-faint">
              <span className="kbd">Ctrl</span>
              <span className="ml-1 mr-2">+</span>
              <span className="kbd">⏎</span>
              <span className="ml-2">to submit</span>
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={cancel}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={submit}
                disabled={!text.trim()}
              >
                Send to LLM
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
