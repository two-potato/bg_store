import type { ReactNode } from "react";
import Link from "next/link";

type ChipProps = {
  children: ReactNode;
  href?: string;
  active?: boolean;
  className?: string;
};

export function Chip({ children, href, active = false, className = "" }: ChipProps) {
  const cls = ["ui-chip", active ? "is-active" : "", className].filter(Boolean).join(" ");

  if (href) {
    return (
      <Link href={href} className={cls}>
        {children}
      </Link>
    );
  }

  return <span className={cls}>{children}</span>;
}
