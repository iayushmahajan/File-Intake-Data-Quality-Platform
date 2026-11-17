// Adapted from shadcn/ui's MIT-licensed React 18 / Tailwind 3 Button.
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

export const buttonVariants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 text-sm font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50",
  { variants: {
    variant: {
      default: "bg-primary text-primary-foreground hover:bg-primary/90",
      accent: "bg-brand text-brand-foreground hover:bg-brand/90",
      outline: "border border-border bg-surface text-foreground hover:bg-secondary",
      ghost: "text-foreground hover:bg-secondary",
    },
    size: { default: "h-11", sm: "h-10 min-h-10 px-3 text-xs" },
  }, defaultVariants: { variant: "default", size: "default" } },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Component = asChild ? Slot : "button";
    return <Component ref={ref} type={asChild ? undefined : type ?? "button"} className={cn(buttonVariants({ variant, size, className }))} {...props} />;
  },
);
Button.displayName = "Button";
