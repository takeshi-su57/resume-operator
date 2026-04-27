import {
  FileSearch,
  Gauge,
  Home,
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
  end?: boolean;
};

const items: NavItem[] = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/run", label: "Run", icon: PlayCircle },
  { to: "/score", label: "Score", icon: Gauge },
  { to: "/bootstrap", label: "Bootstrap", icon: Sparkles },
  { to: "/parse", label: "Parse PDF", icon: FileSearch },
  { to: "/style", label: "Extract Style", icon: Wrench },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
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
      <div className="flex h-10 items-center justify-between px-3 border-b border-border">
        <span className="font-mono text-xs font-bold tracking-wider text-fg">
          resume-operator
        </span>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {items.map((item) => (
          <NavRailLink key={item.to} item={item} />
        ))}
      </nav>
      <div className="mt-auto p-3 text-[0.6875rem] text-fg-faint" data-no-select>
        <div className="flex items-center gap-1">
          <span className="kbd">⌘</span>
          <span className="kbd">K</span>
          <span className="ml-1">command palette</span>
        </div>
      </div>
    </aside>
  );
}

function NavRailLink({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
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
