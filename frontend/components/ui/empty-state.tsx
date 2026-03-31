import type { ReactNode } from "react";
import { Button } from "./button";

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
  icon?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, icon, className = "" }: EmptyStateProps) {
  return (
    <div className={["ui-empty-state", className].filter(Boolean).join(" ")}>
      {icon ? <div className="ui-empty-state__icon">{icon}</div> : null}
      <h2 className="ui-empty-state__title">{title}</h2>
      {description ? <p className="ui-empty-state__desc">{description}</p> : null}
      {action ? (
        <div className="ui-empty-state__action">
          {action.href ? (
            <Button href={action.href} variant="primary">
              {action.label}
            </Button>
          ) : (
            <Button type="button" variant="primary" onClick={action.onClick}>
              {action.label}
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
}
