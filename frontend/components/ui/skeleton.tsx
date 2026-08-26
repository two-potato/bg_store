type SkeletonProps = {
  className?: string;
  width?: string | number;
  height?: string | number;
};

export function Skeleton({ className = "", width, height }: SkeletonProps) {
  return (
    <span
      className={["ui-skeleton", className].filter(Boolean).join(" ")}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={["ui-skeleton-card", className].filter(Boolean).join(" ")} aria-hidden="true">
      <Skeleton className="ui-skeleton-card__image" />
      <div className="ui-skeleton-card__body">
        <Skeleton className="ui-skeleton-card__line ui-skeleton-card__line--title" />
        <Skeleton className="ui-skeleton-card__line ui-skeleton-card__line--sub" />
        <Skeleton className="ui-skeleton-card__line ui-skeleton-card__line--price" />
      </div>
    </div>
  );
}
