import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { ProductCard } from "@/components/product-card";
import {
  getCategories,
  getCollections,
  getProductList,
  normalizeSlugPath,
  pickText,
  type CatalogFilters,
  type CategorySummary,
} from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

type CategoryDetailPageProps = {
  params: Promise<{ slug: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function readSearchParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function buildCategoryHref(path: string, page: number) {
  const normalized = normalizeSlugPath(path);
  if (page <= 1) {
    return `/categories/${normalized}`;
  }
  return `/categories/${normalized}?page=${page}`;
}

function buildCategoryBreadcrumbs(categories: CategorySummary[], path: string) {
  const normalized = normalizeSlugPath(path);
  const byPath = new Map(
    categories.map((category) => [normalizeSlugPath(category.full_slug_path || category.slug), category]),
  );

  return normalized
    .split("/")
    .map((_, index, parts) => parts.slice(0, index + 1).join("/"))
    .map((itemPath) => byPath.get(itemPath))
    .filter(Boolean) as CategorySummary[];
}

export async function generateMetadata({ params }: CategoryDetailPageProps): Promise<Metadata> {
  const slug = (await params).slug || [];
  const path = normalizeSlugPath(slug.join("/"));
  const categories = await getCategories();
  const category = categories.find((item) => normalizeSlugPath(item.full_slug_path || item.slug) === path);

  if (!category) {
    return {
      title: "Категория не найдена",
    };
  }

  return {
    title: category.meta_title || category.hero_title || category.name,
    description: pickText(
      category.meta_description,
      category.hero_text,
      category.description,
      `Категория ${category.name} в каталоге Servio.`,
    ),
  };
}

export default async function CategoryDetailPage({
  params,
  searchParams,
}: CategoryDetailPageProps) {
  const slug = (await params).slug || [];
  const path = normalizeSlugPath(slug.join("/"));
  const page = Math.max(1, Number(readSearchParam((await searchParams).page)) || 1);
  const [categories, collections] = await Promise.all([getCategories(), getCollections()]);
  const category = categories.find((item) => normalizeSlugPath(item.full_slug_path || item.slug) === path);

  if (!category) {
    notFound();
  }

  const productList = await getProductList({
    category_path: path,
    include_descendants: true,
    page,
  } satisfies CatalogFilters);

  const breadcrumbs = buildCategoryBreadcrumbs(categories, path);
  const childCategories = categories.filter((item) => item.parent === category.id).slice(0, 12);
  const featuredBrands = Array.from(
    new Map(
      productList.products
        .filter((product) => product.brand?.slug)
        .map((product) => [product.brand?.slug as string, product.brand]),
    ).values(),
  ).slice(0, 8);
  const relatedCollections = collections.filter((collection) => collection.is_featured).slice(0, 3);

  return (
    <div className="servio-discovery-page">
      <nav className="servio-breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Главная</Link>
        <span>/</span>
        <Link href="/categories">Категории</Link>
        {breadcrumbs.map((crumb, index) => (
          <span key={crumb.id} className="servio-breadcrumbs__item">
            <span>/</span>
            {index === breadcrumbs.length - 1 ? (
              <span>{crumb.name}</span>
            ) : (
              <Link href={`/categories/${crumb.full_slug_path || crumb.slug}`}>{crumb.name}</Link>
            )}
          </span>
        ))}
      </nav>

      <section className="servio-discovery-hero servio-card servio-card--hero">
        <div className="servio-discovery-hero__content">
          <span className="servio-eyebrow">Category detail</span>
          <p className="servio-kicker">SEO и discovery route</p>
          <h1 className="servio-page-title">{category.hero_title || category.name}</h1>
          <p className="servio-copy servio-copy--lead">
            {pickText(
              category.hero_text,
              category.description,
              "Категорийная витрина Servio для long-tail SEO и профессиональных закупок.",
            )}
          </p>
          <div className="servio-chip-row">
            <span className="servio-chip">{category.product_count || productList.products.length} SKU</span>
            <span className="servio-chip">{childCategories.length} подкатегорий</span>
            <span className="servio-chip">{featuredBrands.length} брендов на текущем экране</span>
          </div>
        </div>

        <aside className="servio-discovery-hero__rail">
          {childCategories.length ? (
            <div className="servio-card servio-card--soft">
              <span className="servio-eyebrow">Подкатегории</span>
              <div className="servio-filter-group__chips">
                {childCategories.map((child) => (
                  <Link
                    key={child.id}
                    href={`/categories/${child.full_slug_path || child.slug}`}
                    className="servio-filter-chip"
                  >
                    {child.name}
                  </Link>
                ))}
              </div>
            </div>
          ) : (
            <div className="servio-catalog-stat">
              <strong>1 route</strong>
              <span>линейка уже готова для search и category discovery</span>
            </div>
          )}
        </aside>
      </section>

      {featuredBrands.length ? (
        <section className="servio-card servio-card--soft">
          <span className="servio-eyebrow">Бренды в категории</span>
          <div className="servio-filter-group__chips">
            {featuredBrands.map((brand) => (
              <Link key={brand?.id} href={`/brands/${brand?.slug}`} className="servio-filter-chip">
                {brand?.name}
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {productList.products.length ? (
        <section className="servio-product-grid" aria-label={`Товары категории ${category.name}`}>
          {productList.products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </section>
      ) : (
        <section className="servio-card servio-empty-state">
          <span className="servio-eyebrow">Пустая выдача</span>
          <h2 className="servio-card-title">По категории пока нет опубликованных товаров</h2>
          <p className="servio-copy">
            SEO-маршрут уже заведён. Дальше можно безболезненно наращивать ассортимент и category landing blocks.
          </p>
        </section>
      )}

      <section className="servio-catalog-pagination servio-card servio-card--soft">
        <div>
          <span className="servio-eyebrow">Пагинация</span>
          <h2 className="servio-card-title">Категорийный контур уже живёт на Next.js</h2>
          <p className="servio-copy">
            Эта страница держит SEO и routing, а бизнес-логика выдачи остаётся в backend search layer.
          </p>
        </div>
        <div className="servio-pagination-actions">
          {productList.page > 1 ? (
            <Link
              href={buildCategoryHref(path, productList.page - 1)}
              className="servio-button servio-button--secondary"
            >
              Предыдущая страница
            </Link>
          ) : null}
          {productList.hasNextPage ? (
            <Link
              href={buildCategoryHref(path, productList.page + 1)}
              className="servio-button servio-button--primary"
            >
              Следующая страница
            </Link>
          ) : (
            <span className="servio-pagination-end">Это последний экран по категории.</span>
          )}
        </div>
      </section>

      {category.landing_body ? (
        <section className="servio-card">
          <span className="servio-eyebrow">О категории</span>
          <div className="servio-product-richtext">
            {category.landing_body.split(/\n+/).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}

      {relatedCollections.length ? (
        <section className="servio-discovery-section">
          <div className="servio-related__header">
            <span className="servio-eyebrow">Подборки</span>
            <h2 className="servio-card-title">Рекламные блоки, которые усиливают категорию</h2>
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
                  "Подборка Servio, которая дополняет категорийную навигацию рекламным блоком.",
                )}
                cta="Открыть подборку"
                image={collection.photo}
                imageAlt={collection.name}
                meta={[collection.products_count ? `${collection.products_count} SKU` : "collection surface"]}
              />
            ))}
          </div>
        </section>
      ) : null}

      {category.faq_body ? (
        <section className="servio-card">
          <span className="servio-eyebrow">FAQ</span>
          <h2 className="servio-card-title">{category.faq_title || `FAQ по категории ${category.name}`}</h2>
          <div className="servio-product-richtext">
            {category.faq_body.split(/\n+/).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
