import Link from "next/link";
import type { Metadata } from "next";

import { ProductCard } from "@/components/product-card";
import { Chip, EmptyState } from "@/components/ui";
import {
  getCatalogPageData,
  type BrandSummary,
  type CatalogFilters,
  type CategorySummary,
} from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Каталог",
  description:
    "Каталог Servio для HoReCa и retail: профессиональные товары, бренды и подборки для кухни, сервиса и ежедневной закупки.",
};

type CatalogPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function readSearchParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) return value[0];
  return value;
}

function normalizeFilters(params: Record<string, string | string[] | undefined>): CatalogFilters {
  const page = Number(readSearchParam(params.page));
  return {
    brand: readSearchParam(params.brand),
    category: readSearchParam(params.category),
    series: readSearchParam(params.series),
    is_new: readSearchParam(params.is_new),
    is_promo: readSearchParam(params.is_promo),
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function buildCatalogHref(filters: CatalogFilters, overrides: Partial<CatalogFilters>) {
  const params = new URLSearchParams();
  const next = { ...filters, ...overrides };
  if (next.brand) params.set("brand", next.brand);
  if (next.category) params.set("category", next.category);
  if (next.series) params.set("series", next.series);
  if (next.is_new) params.set("is_new", next.is_new);
  if (next.is_promo) params.set("is_promo", next.is_promo);
  if (next.page && next.page > 1) params.set("page", String(next.page));
  const query = params.toString();
  return query ? `/catalog?${query}` : "/catalog";
}

function selectHeading(
  selectedBrand: BrandSummary | undefined,
  selectedCategory: CategorySummary | undefined,
  filters: CatalogFilters,
) {
  if (selectedCategory) return selectedCategory.name;
  if (selectedBrand) return selectedBrand.name;
  if (filters.is_promo) return "Акции";
  if (filters.is_new) return "Новинки";
  return "Каталог";
}

export default async function CatalogPage({ searchParams }: CatalogPageProps) {
  const filters = normalizeFilters(await searchParams);

  let data: Awaited<ReturnType<typeof getCatalogPageData>> | null = null;
  try {
    data = await getCatalogPageData(filters);
  } catch {
    return (
      <div className="catalog-page">
        <EmptyState
          title="Каталог временно недоступен"
          description="Попробуйте обновить страницу или вернитесь через несколько минут."
          action={{ label: "Обновить", href: "/catalog" }}
        />
      </div>
    );
  }

  const { products, brands, categories, page, hasNextPage } = data;
  const selectedBrand = brands.find((b) => String(b.id) === filters.brand);
  const selectedCategory = categories.find((c) => String(c.id) === filters.category);
  const heading = selectHeading(selectedBrand, selectedCategory, filters);
  const rootCategories = categories.filter((c) => c.parent === null).slice(0, 8);
  const featuredBrands = brands.slice(0, 8);
  const hasActiveFilter = filters.brand || filters.category || filters.series || filters.is_new || filters.is_promo;

  return (
    <div className="catalog-page">

      {/* Breadcrumb */}
      <nav className="catalog-breadcrumb" aria-label="Навигация">
        <Link href="/" className="catalog-breadcrumb__item">Главная</Link>
        <span className="catalog-breadcrumb__sep" aria-hidden="true">/</span>
        {hasActiveFilter ? (
          <>
            <Link href="/catalog" className="catalog-breadcrumb__item">Каталог</Link>
            <span className="catalog-breadcrumb__sep" aria-hidden="true">/</span>
            <span className="catalog-breadcrumb__current" aria-current="page">{heading}</span>
          </>
        ) : (
          <span className="catalog-breadcrumb__current" aria-current="page">Каталог</span>
        )}
      </nav>

      {/* Заголовок */}
      <div className="catalog-head">
        <h1 className="catalog-head__title">{heading}</h1>
        {hasActiveFilter && (
          <Link href="/catalog" className="catalog-head__reset">Сбросить фильтры</Link>
        )}
      </div>

      {/* Фильтры */}
      <div className="catalog-filters" role="search" aria-label="Фильтры каталога">
        <div className="catalog-filter-row">
          <span className="catalog-filter-row__label">Категории</span>
          <div className="catalog-filter-row__chips">
            <Chip href={buildCatalogHref(filters, { category: undefined, page: 1 })} active={!filters.category}>
              Все
            </Chip>
            {rootCategories.map((category) => (
              <Chip
                key={category.id}
                href={buildCatalogHref(filters, { category: String(category.id), page: 1 })}
                active={String(category.id) === filters.category}
              >
                {category.name}
              </Chip>
            ))}
          </div>
        </div>

        <div className="catalog-filter-row">
          <span className="catalog-filter-row__label">Бренды</span>
          <div className="catalog-filter-row__chips">
            <Chip href={buildCatalogHref(filters, { brand: undefined, page: 1 })} active={!filters.brand}>
              Все
            </Chip>
            {featuredBrands.map((brand) => (
              <Chip
                key={brand.id}
                href={buildCatalogHref(filters, { brand: String(brand.id), page: 1 })}
                active={String(brand.id) === filters.brand}
              >
                {brand.name}
              </Chip>
            ))}
          </div>
        </div>

        <div className="catalog-filter-row">
          <span className="catalog-filter-row__label">Подборки</span>
          <div className="catalog-filter-row__chips">
            <Chip
              href={buildCatalogHref(filters, { is_new: filters.is_new ? undefined : "true", page: 1 })}
              active={!!filters.is_new}
            >
              Новинки
            </Chip>
            <Chip
              href={buildCatalogHref(filters, { is_promo: filters.is_promo ? undefined : "true", page: 1 })}
              active={!!filters.is_promo}
            >
              Акции
            </Chip>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="catalog-toolbar" aria-live="polite" aria-atomic="true">
        <p className="catalog-toolbar__count">
          {products.length > 0
            ? `Показано ${products.length} товаров${page > 1 ? `, страница ${page}` : ""}`
            : "Нет товаров по выбранным фильтрам"}
        </p>
      </div>

      {/* Товары */}
      {products.length > 0 ? (
        <section className="servio-product-grid" aria-label="Список товаров">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </section>
      ) : (
        <EmptyState
          title="По выбранным фильтрам ничего нет"
          description="Снимите часть фильтров или вернитесь к общему каталогу."
          action={{ label: "Сбросить фильтры", href: "/catalog" }}
        />
      )}

      {/* Пагинация */}
      {(page > 1 || hasNextPage) && (
        <nav className="catalog-pagination" aria-label="Страницы каталога">
          {page > 1 ? (
            <Link
              href={buildCatalogHref(filters, { page: page - 1 })}
              className="servio-button servio-button--secondary"
              aria-label="Предыдущая страница"
            >
              ← Назад
            </Link>
          ) : (
            <span className="catalog-pagination__spacer" aria-hidden="true" />
          )}
          <span className="catalog-pagination__current" aria-current="page">Страница {page}</span>
          {hasNextPage ? (
            <Link
              href={buildCatalogHref(filters, { page: page + 1 })}
              className="servio-button servio-button--primary"
              aria-label="Следующая страница"
            >
              Вперёд →
            </Link>
          ) : (
            <span className="catalog-pagination__end">Последняя страница</span>
          )}
        </nav>
      )}

    </div>
  );
}
