import { open } from "@tauri-apps/plugin-dialog";
import { FolderOpen, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export type FileFilter = {
  name: string;
  extensions: string[];
};

type FilePickerProps = {
  value: string;
  onChange: (path: string) => void;
  placeholder?: string;
  filters?: FileFilter[];
  className?: string;
};

/**
 * Compact file-picker row — read-only path display with [...] button to
 * open the OS file dialog and an [x] button to clear. The Tauri shell
 * exposes the dialog via `@tauri-apps/plugin-dialog`; in Vite dev mode
 * outside Tauri, the buttons are still clickable but `open()` throws —
 * the component catches and falls back to a no-op so you can browse the
 * UI in a regular browser tab if you ever need to.
 */
export function FilePicker({
  value,
  onChange,
  placeholder = "Select a file…",
  filters,
  className,
}: FilePickerProps) {
  const pick = async () => {
    try {
      const selected = await open({
        multiple: false,
        directory: false,
        filters,
      });
      if (typeof selected === "string") {
        onChange(selected);
      }
    } catch {
      // Tauri API not available (running in plain browser) — silently noop.
    }
  };
  return (
    <div className={cn("flex w-full gap-1.5", className)}>
      <div
        className="input-base flex flex-1 items-center truncate"
        title={value}
      >
        <span className={cn("truncate", !value && "text-fg-faint")}>
          {value || placeholder}
        </span>
      </div>
      <Button
        type="button"
        size="md"
        variant="secondary"
        onClick={pick}
        title="Browse..."
      >
        <FolderOpen className="h-4 w-4" />
      </Button>
      {value && (
        <Button
          type="button"
          size="md"
          variant="ghost"
          onClick={() => onChange("")}
          title="Clear"
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
