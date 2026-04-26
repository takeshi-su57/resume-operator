import * as RadixLabel from "@radix-ui/react-label";
import { forwardRef, type ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/cn";

export const Label = forwardRef<
  HTMLLabelElement,
  ComponentPropsWithoutRef<typeof RadixLabel.Root>
>(({ className, ...props }, ref) => (
  <RadixLabel.Root
    ref={ref}
    className={cn(
      "block font-mono text-xs uppercase tracking-wider text-fg-muted",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";
