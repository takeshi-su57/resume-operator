import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import {
  FileSearch,
  Gauge,
  Home,
  PlayCircle,
  Settings,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/cn";

type Cmd = {
  id: string;
  label: string;
  hint?: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  group: "Navigate";
};

const COMMANDS: Cmd[] = [
  { id: "home", label: "Go to Home", to: "/", icon: Home, group: "Navigate" },
  { id: "run", label: "Tailor a resume", to: "/run", icon: PlayCircle, group: "Navigate" },
  { id: "score", label: "Score against a JD", to: "/score", icon: Gauge, group: "Navigate" },
  {
    id: "bootstrap",
    label: "Bootstrap master from PDF",
    to: "/bootstrap",
    icon: Sparkles,
    group: "Navigate",
  },
  {
    id: "parse",
    label: "Parse a resume PDF",
    to: "/parse",
    icon: FileSearch,
    group: "Navigate",
  },
  {
    id: "style",
    label: "Extract style from .docx",
    to: "/style",
    icon: Wrench,
    group: "Navigate",
  },
  {
    id: "settings",
    label: "Open Settings",
    to: "/settings",
    icon: Settings,
    group: "Navigate",
  },
];

/**
 * Cmd+K command palette. Phase 5 ships navigation only; recent runs
 * + arbitrary actions can come later. Linear/Raycast pattern: dim
 * overlay, centered card, fuzzy search, keyboard-driven (arrows +
 * Enter). Mounted at the App shell so any screen can fire it.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const run = (cmd: Cmd) => {
    setOpen(false);
    navigate(cmd.to);
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 animate-fade-in" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-[20%] -translate-x-1/2",
            "w-[min(640px,90vw)] panel overflow-hidden shadow-xl animate-fade-in",
          )}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description className="sr-only">
            Type to search; arrow keys to navigate; Enter to run.
          </Dialog.Description>
          <Command label="Command palette">
            <Command.Input
              placeholder="Type a command…"
              className={cn(
                "w-full border-b border-border bg-transparent",
                "px-4 py-3 text-sm font-mono outline-none placeholder:text-fg-faint",
              )}
            />
            <Command.List className="max-h-[400px] overflow-y-auto p-1">
              <Command.Empty className="px-4 py-6 text-center text-sm text-fg-faint">
                No commands.
              </Command.Empty>
              <Command.Group
                heading="Navigate"
                className={cn(
                  "py-1",
                  "[&_[cmdk-group-heading]]:px-3",
                  "[&_[cmdk-group-heading]]:py-1",
                  "[&_[cmdk-group-heading]]:text-xs",
                  "[&_[cmdk-group-heading]]:uppercase",
                  "[&_[cmdk-group-heading]]:tracking-wider",
                  "[&_[cmdk-group-heading]]:text-fg-muted",
                )}
              >
                {COMMANDS.map((cmd) => {
                  const Icon = cmd.icon;
                  return (
                    <Command.Item
                      key={cmd.id}
                      value={cmd.label}
                      onSelect={() => run(cmd)}
                      className={cn(
                        "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm",
                        "data-[selected=true]:bg-bg-raised data-[selected=true]:text-fg",
                        "text-fg-muted",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      <span>{cmd.label}</span>
                    </Command.Item>
                  );
                })}
              </Command.Group>
            </Command.List>
            <div
              className="border-t border-border-subtle bg-bg-panel px-3 py-2 text-xs text-fg-faint flex items-center gap-3"
              data-no-select
            >
              <span>
                <span className="kbd">↑</span>
                <span className="kbd ml-0.5">↓</span>
                <span className="ml-1">navigate</span>
              </span>
              <span>
                <span className="kbd">⏎</span>
                <span className="ml-1">run</span>
              </span>
              <span>
                <span className="kbd">Esc</span>
                <span className="ml-1">close</span>
              </span>
              <span className="ml-auto">
                <span className="kbd">⌘</span>
                <span className="kbd">K</span>
              </span>
            </div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
