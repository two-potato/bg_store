import Link from "next/link";

type SortOption = { value: string; label: string };

const SORT_OPTIONS: SortOption[] = [
  { value: "", label: "Популярные" },
  { value: "new", label: "Новинки" },
  { value: "price_asc", label: "Цена ↑" },
  { value: "price_desc", label: "Цена ↓" },
];

type SortBarProps = {
  total: number;
  currentSort?: string;
  basePath: string;
  searchParams?: Record<string, string>;
};

function buildSortHref(basePath: string, searchParams: Record<string, string>, sort: string) {
  const params = new URLSearchParams(searchParams);
  if (sort) {
    params.set("sort", sort);
  } else {
    params.delete("sort");
  }
  params.delete("page");
  const qs = params.toString();
  return qs ? `${basePath}?${qs}` : basePath;
}

export function SortBar({ total, currentSort = "", basePath, searchParams = {} }: SortBarProps) {
  return (
    <div className="ui-sortbar">
      <p className="ui-sortbar__count">
        {total > 0 ? (
          <>Найдено <strong>{total.toLocaleString("ru-RU")}</strong> товаров</>
        ) : (
          "Товары не найдены"
        )}
      </p>
      <div className="ui-sortbar__chips" role="group" aria-label="Сортировка">
        {SORT_OPTIONS.map((option) => {
          const isActive = option.value === currentSort || (option.value === "" && !currentSort);
          return (
            <Link
              key={option.value}
              href={buildSortHref(basePath, searchParams, option.value)}
              className={isActive ? "ui-chip is-active" : "ui-chip"}
              aria-current={isActive ? "true" : undefined}
            >
              {option.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
