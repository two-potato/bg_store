import Link from "next/link";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { ProductCard } from "@/components/product-card";
import { Chip, EmptyState } from "@/components/ui";
import {
  getDiscoveryDirectoryData,
  getProductList,
  pickText,
  type CatalogFilters,
} from "@/lib/catalog-api";

function pluralizeProducts(n: number) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return `${n} товаров`;
  if (mod10 === 1) return `${n} товар`;
  if (mod10 >= 2 && mod10 <= 4) return `${n} товара`;
  return `${n} товаров`;
}

export const dynamic = "force-dynamic";

type SearchPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

const quickQueries = [
  "тарелки для подачи",
  "барное стекло",
  "сервировка hotel buffet",
  "инвентарь для кухни",
  "упаковка takeaway",
];

function readSearchParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function buildSearchHref(query: string, page: number) {
  const params = new URLSearchParams();
  if (query.trim()) {
    params.set("q", query.trim());
  }
  if (page > 1) {
    params.set("page", String(page));
  }
  const search = params.toString();
  return search ? `/search?${search}` : "/search";
}

export async function generateMetadata({ searchParams }: SearchPageProps): Promise<Metadata> {
  const query = readSearchParam((await searchParams).q)?.trim() || "";
  if (!query) {
    return {
      title: "Поиск",
      description: "Поиск по каталогу Servio: товары для HoReCa по названию, бренду или категории.",
    };
  }

  return {
    title: `Поиск: ${query}`,
    description: `Поисковая выдача Servio по запросу «${query}».`,
  };
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const resolvedParams = await searchParams;
  const query = readSearchParam(resolvedParams.q)?.trim() || "";
  const page = Math.max(1, Number(readSearchParam(resolvedParams.page)) || 1);

  const [directory, searchResult] = await Promise.all([
    getDiscoveryDirectoryData(),
    getProductList((query ? { q: query, page } : { page: 1, limit: 6 }) satisfies CatalogFilters),
  ]);

  const rootCategories = directory.categories.filter((category) => category.parent === null).slice(0, 5);
  const featuredCollections = directory.collections.filter((collection) => collection.is_featured).slice(0, 3);
  const featuredBrands = directory.brands.slice(0, 3);

  return (
    <div className="servio-discovery-page">
      <section className="search-hero-compact">
        <h1 className="search-hero-compact__title">
          {query ? `«${query}»` : "Поиск по каталогу"}
        </h1>

        <form action="/search" className="servio-search-form">
          <input
            type="search"
            name="q"
            defaultValue={query}
            placeholder="Например: тарелки для подачи, барное стекло, упаковка takeaway"
            className="servio-search-form__input"
            aria-label="Поиск по каталогу Servio"
          />
          <button type="submit" className="servio-button servio-button--primary">
            Найти
          </button>
        </form>

        <div className="search-category-chips">
          {quickQueries.map((item) => (
            <Chip key={item} href={buildSearchHref(item, 1)} active={item === query}>
              {item}
            </Chip>
          ))}
        </div>
      </section>

      {query && (
        <div className="search-results-toolbar">
          <span>{pluralizeProducts(searchResult.products.length)} по запросу «{query}»</span>
          <Link href="/search" className="ui-chip">Сбросить</Link>
        </div>
      )}

      {query ? (
        <>

          {searchResult.products.length ? (
            <section className="servio-product-grid" aria-label={`Результаты поиска по запросу ${query}`}>
              {searchResult.products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </section>
          ) : (
            <EmptyState
              title="По запросу ничего не найдено"
              description="Попробуйте упростить запрос или поискать по категории."
              action={{ label: "Смотреть весь каталог", href: "/catalog" }}
            />
          )}

          <section className="servio-catalog-pagination servio-card servio-card--soft">
            <div className="servio-pagination-actions">
              {page > 1 ? (
                <Link href={buildSearchHref(query, page - 1)} className="servio-button servio-button--secondary">
                  Предыдущая страница
                </Link>
              ) : null}
              {searchResult.hasNextPage ? (
                <Link href={buildSearchHref(query, page + 1)} className="servio-button servio-button--primary">
                  Следующая страница
                </Link>
              ) : (
                <span className="servio-pagination-end">Это последний экран выдачи.</span>
              )}
            </div>
          </section>
        </>
      ) : (
        <>
          <section className="servio-product-grid" aria-label="Популярные товары для старта поиска">
            {searchResult.products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </section>

          <section className="servio-discovery-grid servio-discovery-grid--spotlight">
            {featuredCollections.map((collection) => (
              <DiscoveryEntityCard
                key={collection.id}
                href={`/collections/${collection.slug}`}
                kicker="Коллекция"
                title={collection.hero_title || collection.name}
                copy={pickText(
                  collection.hero_text,
                  collection.description,
                  "Подборка Servio для быстрого входа в закупочный сценарий.",
                )}
                cta="Открыть подборку"
                image={collection.photo}
                imageAlt={collection.name}
                meta={[collection.products_count ? `${collection.products_count} SKU` : "подборка Servio"]}
              />
            ))}
            {featuredBrands.map((brand) => (
              <DiscoveryEntityCard
                key={brand.id}
                href={`/brands/${brand.slug}`}
                kicker="Бренд"
                title={brand.name}
                copy={pickText(
                  brand.description,
                  brand.landing_body,
                  "Быстрый вход в ассортимент по бренду без перегруженной выдачи.",
                )}
                cta="Открыть бренд"
                image={brand.photo}
                imageAlt={brand.name}
                imageFit="contain"
                fallback={brand.name}
                meta={[brand.products_count ? `${brand.products_count} SKU` : "бренд в каталоге"]}
              />
            ))}
          </section>

          {rootCategories.length ? (
            <section className="servio-card servio-card--soft">
              <span className="servio-eyebrow">Категории</span>
              <div className="servio-filter-group__chips">
                {rootCategories.map((category) => (
                  <Link
                    key={category.id}
                    href={`/categories/${category.full_slug_path || category.slug}`}
                    className="servio-filter-chip"
                  >
                    {category.name}
                  </Link>
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
