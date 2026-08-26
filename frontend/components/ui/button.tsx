import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import Link from "next/link";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

type BaseButtonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
  className?: string;
};

type ButtonProps = BaseButtonProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };
type LinkButtonProps = BaseButtonProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

type Props = ButtonProps | LinkButtonProps;

const variantClass: Record<ButtonVariant, string> = {
  primary: "ui-btn--primary",
  secondary: "ui-btn--secondary",
  ghost: "ui-btn--ghost",
  danger: "ui-btn--danger",
};

const sizeClass: Record<ButtonSize, string> = {
  sm: "ui-btn--sm",
  md: "ui-btn--md",
  lg: "ui-btn--lg",
};

export function Button({ variant = "primary", size = "md", className = "", children, ...rest }: Props) {
  const cls = ["ui-btn", variantClass[variant], sizeClass[size], className].filter(Boolean).join(" ");

  if ("href" in rest && rest.href !== undefined) {
    const { href, ...linkRest } = rest as LinkButtonProps;
    return (
      <Link href={href} className={cls} {...(linkRest as object)}>
        {children}
      </Link>
    );
  }

  return (
    <button className={cls} {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}>
      {children}
    </button>
  );
}
