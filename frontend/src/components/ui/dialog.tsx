// Adapted from shadcn/ui's MIT-licensed React 18 / Tailwind 3 Dialog.
import * as React from "react";
import * as Primitive from "@radix-ui/react-dialog";
import { cn } from "../../lib/utils";

export const Dialog = Primitive.Root;
export const DialogTrigger = Primitive.Trigger;
export const DialogClose = Primitive.Close;
export const DialogTitle = Primitive.Title;
export const DialogDescription = Primitive.Description;
export const DialogContent = React.forwardRef<React.ElementRef<typeof Primitive.Content>, React.ComponentPropsWithoutRef<typeof Primitive.Content>>(
  ({ className, children, ...props }, ref) => (
    <Primitive.Portal>
      <Primitive.Overlay className="dialog-overlay fixed inset-0 z-40 bg-overlay/65" />
      <Primitive.Content ref={ref} className={cn("surface-context dialog-content fixed left-1/2 top-1/2 z-50 w-[calc(100%_-_2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border bg-surface p-6 text-foreground shadow-panel", className)} {...props}>
        {children}
      </Primitive.Content>
    </Primitive.Portal>
  ),
);
DialogContent.displayName = "DialogContent";
