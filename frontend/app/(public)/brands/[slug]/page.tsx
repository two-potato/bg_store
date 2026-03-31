import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { ProductCard } from "@/components/product-card";
import {
  getBrandBySlug,
  getCollections,
  getCategories,
  getProductList,
  normalizeAssetUrl,
  pickText,
  type CatalogFilters,
  type CategorySummary,
} from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

type BrandDetailPageProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function readSearchParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function buildBrandHref(slug: string, page: number) {
  if (page <= 1) {
    return `/brands/${slug}`;
  }
  return `/brands/${slug}?page=${page}`;
}

function uniqueCategoriesFromProducts(categories: CategorySummary[], categoryIds: number[]) {
  const idSet = new Set(categoryIds);
  return categories.filter((category) => idSet.has(category.id)).slice(0, 8);
}

export async function generateMetadata({ params }: BrandDetailPageProps): Promise<Metadata> {
  const { slug } = await params;
  const brand = await getBrandBySlug(slug);

  if (!brand) {
    return {
      title: "Бренд не найден",
    };
  }

  return {
    title: brand.meta_title || brand.name,
    description: pickText(
      brand.meta_description,
      brand.description,
      brand.landing_body,
      `Брендовая витрина ${brand.name} в каталоге Servio.`,
    ),
  };
}

export default async function BrandDetailPage({ params, searchParams }: BrandDetailPageProps) {
  const { slug } = await params;
  const page = Math.max(1, Number(readSearchParam((await searchParams).page)) || 1);
  const brand = await getBrandBySlug(slug);

  if (!brand) {
    notFound();
  }

  const [productList, collections, categories] = await Promise.all([
    getProductList({ brand_slug: brand.slug, page } satisfies CatalogFilters),
    getCollections(),
    getCategories(),
  ]);

  const relatedCollections = collections.filter((collection) => collection.is_featured).slice(0, 3);
  const brandCategories = uniqueCategoriesFromProducts(
    categories,
    productList.products.map((product) => product.category_detail?.id).filter(Boolean) as number[],
  );

  return (
    <div className="servio-discovery-page">
      <section className="servio-brand-hero servio-card servio-card--hero">
        <div className="servio-brand-hero__logo-wrap">
          {brand.photo ? (
            <img
              src={normalizeAssetUrl(brand.photo)}
              alt={brand.name}
              className="servio-brand-hero__logo"
            />
          ) : (
            <div className="servio-brand-hero__fallback">{brand.name.slice(0, 1).toUpperCase()}</div>
          )}
        </div>

        <div className="servio-brand-hero__copy">
          <span className="servio-eyebrow">Brand detail</span>
          <p className="servio-kicker">Брендовая витрина Servio</p>
          <h1 className="servio-page-title">{brand.name}</h1>
          <p className="servio-copy servio-copy--lead">
            {pickText(
              brand.description,
              brand.landing_body,
              "Профессиональная линейка товаров для кухни, сервиса, бара и repeat-purchase сценариев закупки.",
            )}
          </p>

          <div className="servio-chip-row">
            <span className="servio-chip">{brand.products_count || productList.products.length} SKU</span>
            <span className="servio-chip">
              {brand.categories_count || brandCategories.length || 1} категорий
            </span>
            <span className="servio-chip">{brand.collections_count || relatedCollections.length} коллекций</span>
          </div>

          <div className="servio-actions">
            <Link href={`/catalog?brand=${brand.id}`} className="servio-button servio-button--primary">
              Открыть в каталоге
            </Link>
            <Link href="/brands" className="servio-button servio-button--secondary">
              Все бренды
            </Link>
          </div>
        </div>
      </section>

      {brandCategories.length ? (
        <section className="servio-card servio-card--soft">
          <span className="servio-eyebrow">Категории бренда</span>
          <div className="servio-filter-group__chips">
            {brandCategories.map((category) => (
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

      {productList.products.length ? (
        <section className="servio-product-grid" aria-label={`Товары бренда ${brand.name}`}>
          {productList.products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </section>
      ) : (
        <section className="servio-card servio-empty-state">
          <span className="servio-eyebrow">Пустая выдача</span>
          <h2 className="servio-card-title">У бренда пока нет опубликованных SKU</h2>
          <p className="servio-copy">
            Каркас brand-first discovery уже на месте. Когда позиции появятся в backend-каталоге, витрина начнёт
            показывать их автоматически.
          </p>
        </section>
      )}

      <section className="servio-catalog-pagination servio-card servio-card--soft">
        <div>
          <span className="servio-eyebrow">Пагинация</span>
          <h2 className="servio-card-title">Продолжаем brand-first migration</h2>
          <p className="servio-copy">
            Брендовые страницы уже работают на Next.js, а фильтрация и данные остаются в backend-контуре.
          </p>
        </div>
        <div className="servio-pagination-actions">
          {productList.page > 1 ? (
            <Link
              href={buildBrandHref(brand.slug, productList.page - 1)}
              className="servio-button servio-button--secondary"
            >
              Предыдущая страница
            </Link>
          ) : null}
          {productList.hasNextPage ? (
            <Link
              href={buildBrandHref(brand.slug, productList.page + 1)}
              className="servio-button servio-button--primary"
            >
              Следующая страница
            </Link>
          ) : (
            <span className="servio-pagination-end">Это последний экран по бренду.</span>
          )}
        </div>
      </section>

      {brand.landing_body ? (
        <section className="servio-card">
          <span className="servio-eyebrow">О бренде</span>
          <div className="servio-product-richtext">
            {brand.landing_body.split(/\n+/).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}

      {relatedCollections.length ? (
        <section className="servio-discovery-section">
          <div className="servio-related__header">
            <span className="servio-eyebrow">Коллекции</span>
            <h2 className="servio-card-title">Подборки, которые усиливают бренд в discovery-цепочке</h2>
          </div>
          <div className="servio-discovery-grid servio-discovery-grid--spotlight">
            {relatedCollections.map((collection) => (
              <DiscoveryEntityCard
                key={collection.id}
                href={`/collections/${collection.slug}`}
                kicker="Коллекция"
                title={collection.hero_title || collection.name}
                copy={pickText(
                  collection.hero_text,
                  collection.description,
                  "Готовая подборка для сценарной закупки в духе старой витрины Servio.",
                )}
                cta="Открыть подборку"
                image={collection.photo}
                imageAlt={collection.name}
                meta={[
                  collection.products_count ? `${collection.products_count} SKU` : "мерчандайзинговая подборка",
                ]}
              />
            ))}
          </div>
        </section>
      ) : null}

      {brand.faq_body ? (
        <section className="servio-card">
          <span className="servio-eyebrow">FAQ</span>
          <h2 className="servio-card-title">{brand.faq_title || `FAQ по бренду ${brand.name}`}</h2>
          <div className="servio-product-richtext">
            {brand.faq_body.split(/\n+/).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
