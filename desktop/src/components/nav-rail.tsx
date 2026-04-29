import {
  FileSearch,
  Gauge,
  PlayCircle,
  Settings as SettingsIcon,
  Sparkles,
  Wrench,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/cn";

type NavItem = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  enabled: boolean;
  hint?: string;
};

const items: NavItem[] = [
  { to: "/run", label: "Run", icon: PlayCircle, enabled: true },
  { to: "/score", label: "Score", icon: Gauge, enabled: true },
  { to: "/bootstrap", label: "Bootstrap", icon: Sparkles, enabled: false, hint: "Phase 5" },
  { to: "/parse", label: "Parse PDF", icon: FileSearch, enabled: false, hint: "Phase 5" },
  { to: "/style", label: "Extract Style", icon: Wrench, enabled: false, hint: "Phase 5" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, enabled: true },
];

export function NavRail({ className }: { className?: string }) {
  return (
    <aside
      className={cn(
        "flex flex-col bg-bg-panel border-r border-border",
        className,
      )}
      data-no-select
    >
      <div className="flex h-10 items-center px-3 border-b border-border">
        <span className="font-mono text-xs font-bold tracking-wider text-fg">
          resume-operator
        </span>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {items.map((item) => (
          <NavRailLink key={item.to} item={item} />
        ))}
      </nav>
    </aside>
  );
}

function NavRailLink({ item }: { item: NavItem }) {
  const Icon = item.icon;
  if (!item.enabled) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-fg-faint",
          "cursor-not-allowed",
        )}
        title={item.hint ? `coming in ${item.hint}` : undefined}
      >
        <Icon className="h-4 w-4" />
        <span className="flex-1">{item.label}</span>
        {item.hint && (
          <span className="text-[0.6875rem] text-fg-faint">{item.hint}</span>
        )}
      </div>
    );
  }
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
          isActive
            ? "bg-bg-raised text-fg"
            : "text-fg-muted hover:bg-bg-raised hover:text-fg",
        )
      }
    >
      <Icon className="h-4 w-4" />
      <span>{item.label}</span>
    </NavLink>
  );
}
