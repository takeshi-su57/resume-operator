import * as Toast from "@radix-ui/react-toast";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

import { cn } from "@/lib/cn";
import { useToaster, type ToastKind } from "@/state/toaster";

const ICONS: Record<ToastKind, React.ComponentType<{ className?: string }>> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

const ACCENTS: Record<ToastKind, string> = {
  success: "border-success/40 bg-success/10",
  error: "border-danger/40 bg-danger/10",
  info: "border-border bg-bg-panel",
};

const ICON_COLOR: Record<ToastKind, string> = {
  success: "text-success",
  error: "text-danger",
  info: "text-fg-muted",
};

/**
 * Bottom-right toast viewport. Mounted once at App.tsx so any screen can
 * fire `notify(...)` and the resulting toast lands here. Each Radix
 * `Toast.Root` controls its own auto-dismiss timer; closing one (manual
 * or auto) drops it from the Zustand queue.
 */
export function Toaster() {
  const toasts = useToaster((s) => s.toasts);
  const dismiss = useToaster((s) => s.dismiss);

  return (
    <Toast.Provider swipeDirection="right">
      {toasts.map((toast) => {
        const Icon = ICONS[toast.kind];
        return (
          <Toast.Root
            key={toast.id}
            duration={toast.duration}
            onOpenChange={(open) => {
              if (!open) dismiss(toast.id);
            }}
            className={cn(
              "panel grid grid-cols-[16px_1fr_16px] items-start gap-2 px-3 py-2.5 shadow-lg",
              "data-[state=open]:animate-fade-in",
              ACCENTS[toast.kind],
            )}
          >
            <Icon className={cn("h-4 w-4 mt-0.5", ICON_COLOR[toast.kind])} />
            <div className="min-w-0">
              <Toast.Title className="text-sm font-bold text-fg">
                {toast.title}
              </Toast.Title>
              {toast.description && (
                <Toast.Description className="mt-0.5 text-xs text-fg-dim leading-relaxed">
                  {toast.description}
                </Toast.Description>
              )}
            </div>
            <Toast.Close
              aria-label="Close"
              className="text-fg-faint hover:text-fg"
            >
              <X className="h-3.5 w-3.5" />
            </Toast.Close>
          </Toast.Root>
        );
      })}
      <Toast.Viewport
        className={cn(
          "fixed bottom-4 right-4 z-50 flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2 outline-none",
        )}
      />
    </Toast.Provider>
  );
}
