import { Loader2, Sparkles } from "lucide-react";

import { cn } from "@/lib/cn";
import {
  BUILTIN_PREFIX,
  isBuiltinIdentifier,
  useBuiltinStyles,
  type BuiltinStyle,
} from "@/lib/api";

type Props = {
  /** Current path/identifier the parent form holds. Used so the
   * matching chip renders selected. */
  value: string;
  onPick: (identifier: string, style: BuiltinStyle) => void;
  className?: string;
};

/**
 * Bundled-style chip selector — sits above the Style file picker on the
 * Run and Extract Style screens. Reads the catalog from
 * `GET /api/styles/builtin` (cached forever via React Query staleTime)
 * and renders one button per preset; clicking emits the
 * `builtin:<name>` identifier the backend recognises plus the parsed
 * `StyleTemplate` so the screen can render a preview without an extra
 * fetch.
 */
export function BuiltinStylePicker({ value, onPick, className }: Props) {
  const { data, isLoading, isError } = useBuiltinStyles();

  if (isError) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      <span className="flex items-center gap-1 text-[11px] uppercase tracking-wider text-fg-muted">
        <Sparkles className="h-3 w-3" />
        Built-in
      </span>
      {isLoading && (
        <Loader2 className="h-3 w-3 animate-spin text-fg-faint" />
      )}
      {data?.styles.map((style) => {
        const identifier = `${BUILTIN_PREFIX}${style.name}`;
        const selected = value === identifier;
        return (
          <button
            key={style.name}
            type="button"
            onClick={() => onPick(identifier, style)}
            className={cn(
              "rounded-sm border px-2 py-0.5 text-xs transition-colors",
              selected
                ? "border-accent bg-accent/10 text-accent"
                : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
            )}
            title={style.description}
          >
            {style.label}
          </button>
        );
      })}
    </div>
  );
}

export { isBuiltinIdentifier };
