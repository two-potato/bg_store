import type { ReactNode } from "react";

type CatalogGridProps = {
  children: ReactNode;
  className?: string;
};

export function CatalogGrid({ children, className = "" }: CatalogGridProps) {
  return (
    <div className={["ui-cat-grid", className].filter(Boolean).join(" ")}>
      {children}
    </div>
  );
}
