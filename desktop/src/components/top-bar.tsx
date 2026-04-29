import { useHealth } from "@/lib/api";
import { cn } from "@/lib/cn";

export function TopBar() {
  const { data, isError } = useHealth();
  const ok = !!data && !isError;
  return (
    <header
      className="flex h-10 items-center justify-end gap-3 border-b border-border bg-bg-panel px-3"
      data-no-select
    >
      <div className="flex items-center gap-1.5 text-xs text-fg-muted">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            ok ? "bg-success" : "bg-danger",
          )}
        />
        <span>
          engine{" "}
          {ok ? (
            <>
              <span className="text-fg">ok</span>{" "}
              <span className="text-fg-dim">·</span>{" "}
              <span className="text-fg">{data!.llm_provider}</span>{" "}
              <span className="text-fg-dim">/</span>{" "}
              <span className="text-fg">{data!.llm_model}</span>
            </>
          ) : (
            <span className="text-danger">offline</span>
          )}
        </span>
      </div>
    </header>
  );
}
