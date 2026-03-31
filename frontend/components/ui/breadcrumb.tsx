import Link from "next/link";

type BreadcrumbItem = {
  label: string;
  href?: string;
};

type BreadcrumbProps = {
  items: BreadcrumbItem[];
  className?: string;
};

export function Breadcrumb({ items, className = "" }: BreadcrumbProps) {
  return (
    <nav
      className={["ui-breadcrumb", className].filter(Boolean).join(" ")}
      aria-label="Breadcrumb"
    >
      <ol className="ui-breadcrumb__list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={item.label} className="ui-breadcrumb__item">
              {!isLast && item.href ? (
                <Link href={item.href} className="ui-breadcrumb__link">
                  {item.label}
                </Link>
              ) : (
                <span className="ui-breadcrumb__current" aria-current={isLast ? "page" : undefined}>
                  {item.label}
                </span>
              )}
              {!isLast ? (
                <span className="ui-breadcrumb__sep" aria-hidden="true">/</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
