import * as Dialog from "@radix-ui/react-dialog";
import { Eye, FileText, Loader2, X } from "lucide-react";
import { useState } from "react";

import { RevealInFolderButton } from "@/components/reveal-in-folder-button";
import { Button } from "@/components/ui/button";
import { YamlTree } from "@/components/yaml-tree";
import { useYamlFile } from "@/lib/api";
import { cn } from "@/lib/cn";

type Props = {
  /** Path to a YAML file. The dialog only fetches when open. */
  path: string;
  /** Render the trigger button as a compact icon-only chip. Default
   * shows label + icon. */
  iconOnly?: boolean;
  triggerClassName?: string;
};

/**
 * Trigger button + Radix Dialog that previews a YAML file as a tree.
 *
 * The dialog mounts lazily via Radix's controlled-open API so the
 * `useYamlFile` query doesn't fire until the user actually clicks
 * Preview. Closing the dialog drops the React Query cache key
 * automatically on the next mount cycle, so re-opening always pulls
 * fresh — handy when Bruno edits the YAML between previews.
 */
export function YamlPreviewDialog({ path, iconOnly, triggerClassName }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={!path}
          title={path ? `Preview ${path}` : "Pick a YAML to preview"}
          className={cn(triggerClassName)}
        >
          <Eye className="h-3.5 w-3.5" />
          {!iconOnly && <span>Preview</span>}
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 animate-fade-in" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-[8%] -translate-x-1/2",
            "w-[min(820px,92vw)] max-h-[84vh] panel overflow-hidden shadow-xl animate-fade-in flex flex-col",
          )}
        >
          {open && <DialogBody path={path} onClose={() => setOpen(false)} />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function DialogBody({ path, onClose }: { path: string; onClose: () => void }) {
  const query = useYamlFile(path, { enabled: !!path });

  return (
    <>
      <div className="flex items-start gap-3 border-b border-border px-4 py-3">
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-fg-muted" />
        <div className="min-w-0 flex-1">
          <Dialog.Title className="text-sm font-bold text-fg">
            YAML preview
          </Dialog.Title>
          <Dialog.Description
            className="mt-0.5 truncate font-mono text-xs text-fg-dim"
            title={path}
          >
            {query.data?.path ?? path}
          </Dialog.Description>
        </div>
        <RevealInFolderButton path={path} variant="ghost" size="sm" />
        <Dialog.Close asChild>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onClose}
            title="Close"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </Dialog.Close>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {query.isLoading && (
          <div className="flex h-full items-center justify-center text-xs text-fg-dim">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Reading file…
          </div>
        )}
        {query.isError && (
          <p className="text-xs text-danger">
            {query.error instanceof Error
              ? query.error.message
              : "Failed to read file."}
          </p>
        )}
        {query.data && (
          <YamlTree data={query.data.content} defaultOpenDepth={1} />
        )}
      </div>
    </>
  );
}
