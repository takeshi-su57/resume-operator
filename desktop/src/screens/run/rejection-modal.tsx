import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Props = {
  open: boolean;
  onSubmit: (reason: string) => void;
  onCancel: () => void;
};

/**
 * Optional reason capture after the user rejects a proposal. Empty
 * reason is fine — the server records the rejection regardless and
 * the LLM uses whatever reason is given (if any) to avoid the same
 * idea on the next iteration. Skipping with empty submits.
 */
export function RejectionModal({ open, onSubmit, onCancel }: Props) {
  const [text, setText] = useState("");
  const submit = (value: string) => {
    onSubmit(value);
    setText("");
  };
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onCancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 animate-fade-in" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
            "w-[min(560px,90vw)] panel p-6 animate-fade-in shadow-xl",
          )}
        >
          <Dialog.Title className="text-sm font-bold text-fg">
            Why reject?
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-xs text-fg-dim leading-relaxed">
            Optional — helps the LLM avoid the same idea next iteration. Hit
            Skip to reject without explanation.
          </Dialog.Description>

          <input
            autoFocus
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder='e.g. "Already covered by exp-1-b3"'
            className="mt-3 w-full input-base font-mono"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit(text);
              }
              if (e.key === "Escape") {
                e.preventDefault();
                onCancel();
              }
            }}
          />

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => submit("")}>
              Skip
            </Button>
            <Button variant="primary" onClick={() => submit(text)}>
              Send
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
