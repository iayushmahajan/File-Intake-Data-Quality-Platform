// Adapted from shadcn/ui's MIT-licensed Tailwind 3 Badge.
import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium", {
  variants: { variant: {
    default: "border-border bg-secondary text-foreground",
    outline: "border-current/25 text-inherit",
    success: "border-success/30 bg-success/10 text-success",
    warning: "border-warning/30 bg-warning/10 text-warning",
    error: "border-danger/30 bg-danger/10 text-danger",
  } }, defaultVariants: { variant: "default" },
});
export function Badge({ className, variant, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
