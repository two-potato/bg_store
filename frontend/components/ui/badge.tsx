import type { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "neutral";

type BadgeProps = {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
};

const variantClass: Record<BadgeVariant, string> = {
  default: "ui-badge--default",
  success: "ui-badge--success",
  warning: "ui-badge--warning",
  danger: "ui-badge--danger",
  neutral: "ui-badge--neutral",
};

export function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span className={["ui-badge", variantClass[variant], className].filter(Boolean).join(" ")}>
      {children}
    </span>
  );
}
