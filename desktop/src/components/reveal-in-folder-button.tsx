import { FolderOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Props = {
  path: string;
  label?: string;
  variant?: "secondary" | "ghost";
  size?: "sm" | "md";
  className?: string;
};

/**
 * Reveals `path` in the OS file manager. On Windows the file is
 * pre-selected via `explorer.exe /select,<path>`; other platforms open
 * the parent directory. The `reveal_in_explorer` Tauri command in
 * `src-tauri/src/lib.rs` implements both branches; outside Tauri
 * (browser dev mode) the call no-ops silently.
 */
export function RevealInFolderButton({
  path,
  label = "Reveal",
  variant = "ghost",
  size = "sm",
  className,
}: Props) {
  const reveal = async () => {
    if (!path) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("reveal_in_explorer", { path });
    } catch {
      // Outside Tauri (dev browser) — silently no-op.
    }
  };
  return (
    <Button
      type="button"
      size={size}
      variant={variant}
      onClick={reveal}
      title={`Reveal in file manager: ${path}`}
      className={cn(className)}
    >
      <FolderOpen className="h-3.5 w-3.5" />
      {label}
    </Button>
  );
}
