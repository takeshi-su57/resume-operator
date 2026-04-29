import { FolderOpen, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";

export type FileFilter = {
  name: string;
  extensions: string[];
};

export type FilePickerMode = "open-file" | "save-file" | "directory";

type FilePickerProps = {
  value: string;
  onChange: (path: string) => void;
  placeholder?: string;
  filters?: FileFilter[];
  className?: string;
  mode?: FilePickerMode;
  /** Suggested filename when mode === "save-file". */
  defaultName?: string;
};

const TOOLTIPS: Record<FilePickerMode, string> = {
  "open-file": "Browse...",
  "save-file": "Save as...",
  directory: "Choose folder...",
};

/**
 * Compact path-picker row — text input + [Browse] button + [x] Clear.
 *
 * In Tauri, [Browse] opens an OS dialog whose flavor follows `mode`:
 * a file-open dialog ("open-file"), a save-as dialog ("save-file"), or
 * a directory chooser ("directory"). All three flow through
 * `@tauri-apps/plugin-dialog`. In plain-browser dev mode (`pnpm dev`,
 * no Tauri runtime), the dialog plugin throws because
 * `window.__TAURI_INTERNALS__` doesn't exist — we catch it and let the
 * user type a path into the input directly. The dialog plugin module
 * is dynamically imported so loading it never crashes the bundle when
 * the Tauri runtime is absent.
 */
export function FilePicker({
  value,
  onChange,
  placeholder = "Select a file…",
  filters,
  className,
  mode = "open-file",
  defaultName,
}: FilePickerProps) {
  const pick = async () => {
    try {
      const dialog = await import("@tauri-apps/plugin-dialog");
      let selected: string | null | undefined;
      if (mode === "save-file") {
        selected = await dialog.save({
          defaultPath: value || defaultName,
          filters,
        });
      } else if (mode === "directory") {
        const result = await dialog.open({ multiple: false, directory: true });
        selected = typeof result === "string" ? result : null;
      } else {
        const result = await dialog.open({
          multiple: false,
          directory: false,
          filters,
        });
        selected = typeof result === "string" ? result : null;
      }
      if (typeof selected === "string") {
        onChange(selected);
      }
    } catch (err) {
      // Most common cause: not running inside Tauri (plain `pnpm dev`).
      // Log so devtools surfaces the real reason if something else
      // breaks; user can still type a path into the input by hand.
      console.warn(
        "[FilePicker] OS dialog unavailable — type the path manually instead.",
        err,
      );
    }
  };
  return (
    <div className={cn("flex w-full gap-1.5", className)}>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        spellCheck={false}
        autoCorrect="off"
        autoCapitalize="off"
        title={value}
        className="flex-1"
      />
      <Button
        type="button"
        size="md"
        variant="secondary"
        onClick={pick}
        title={TOOLTIPS[mode]}
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
