import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { ProductCard } from "@/components/product-card";
import {
  getCollectionBySlug,
  getCollections,
  getProductList,
  normalizeAssetUrl,
  pickText,
  type CatalogFilters,
} from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

type CollectionDetailPageProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function readSearchParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function buildCollectionHref(slug: string, page: number) {
  if (page <= 1) {
    return `/collections/${slug}`;
  }
  return `/collections/${slug}?page=${page}`;
}

export async function generateMetadata({ params }: CollectionDetailPageProps): Promise<Metadata> {
  const { slug } = await params;
  const collection = await getCollectionBySlug(slug);

  if (!collection) {
    return {
      title: "Коллекция не найдена",
    };
  }

  return {
    title: collection.meta_title || collection.hero_title || collection.name,
    description: pickText(
      collection.meta_description,
      collection.hero_text,
      collection.description,
      `Подборка ${collection.name} в storefront Servio.`,
    ),
  };
}

export default async function CollectionDetailPage({
  params,
  searchParams,
}: CollectionDetailPageProps) {
  const { slug } = await params;
  const page = Math.max(1, Number(readSearchParam((await searchParams).page)) || 1);
  const collection = await getCollectionBySlug(slug);

  if (!collection) {
    notFound();
  }

  const [productList, allCollections] = await Promise.all([
    getProductList({ collection_slug: collection.slug, page } satisfies CatalogFilters),
    getCollections(),
  ]);

  const relatedCollections = allCollections
    .filter((item) => item.slug !== collection.slug)
    .slice(0, 3);

  return (
    <div className="servio-discovery-page">
      <section className="servio-discovery-hero servio-card servio-card--hero">
        <div className="servio-discovery-hero__content">
          <span className="servio-eyebrow">Collection detail</span>
          <p className="servio-kicker">Сценарная подборка Servio</p>
          <h1 className="servio-page-title">{collection.hero_title || collection.name}</h1>
          <p className="servio-copy servio-copy--lead">
            {pickText(
              collection.hero_text,
              collection.description,
              "Кураторская подборка для запуска, сезонных кампаний и repeat purchase сценариев.",
            )}
          </p>
          <div className="servio-chip-row">
            <span className="servio-chip">
              {collection.products_count || productList.products.length} SKU в подборке
            </span>
            <span className="servio-chip">
              {collection.is_featured ? "featured placement" : "active merchandising surface"}
            </span>
          </div>
          <div className="servio-actions">
            <Link href="/catalog" className="servio-button servio-button--primary">
              Открыть каталог
            </Link>
            <Link href="/collections" className="servio-button servio-button--secondary">
              Все коллекции
            </Link>
          </div>
        </div>

        <aside className="servio-discovery-hero__rail">
          <div className="servio-discovery-visual">
            {collection.photo ? (
              <img
                src={normalizeAssetUrl(collection.photo)}
                alt={collection.name}
                className="servio-discovery-visual__image"
              />
            ) : (
              <div className="servio-discovery-visual__fallback">Servio</div>
            )}
          </div>
        </aside>
      </section>

      {productList.products.length ? (
        <section className="servio-product-grid" aria-label={`Состав коллекции ${collection.name}`}>
          {productList.products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </section>
      ) : (
        <section className="servio-card servio-empty-state">
          <span className="servio-eyebrow">Пустая подборка</span>
          <h2 className="servio-card-title">В подборке пока нет доступных товаров</h2>
          <p className="servio-copy">
            Merchandising surface уже существует, поэтому новые SKU появятся здесь автоматически после публикации в
            backend-каталоге.
          </p>
        </section>
      )}

      <section className="servio-catalog-pagination servio-card servio-card--soft">
        <div>
          <span className="servio-eyebrow">Пагинация</span>
          <h2 className="servio-card-title">Коллекции уже переведены на новый storefront</h2>
          <p className="servio-copy">
            Дальше здесь можно безболезненно наращивать merchandising и recommendation surfaces.
          </p>
        </div>
        <div className="servio-pagination-actions">
          {productList.page > 1 ? (
            <Link
              href={buildCollectionHref(collection.slug, productList.page - 1)}
              className="servio-button servio-button--secondary"
            >
              Предыдущая страница
            </Link>
          ) : null}
          {productList.hasNextPage ? (
            <Link
              href={buildCollectionHref(collection.slug, productList.page + 1)}
              className="servio-button servio-button--primary"
            >
              Следующая страница
            </Link>
          ) : (
            <span className="servio-pagination-end">Это последний экран по подборке.</span>
          )}
        </div>
      </section>

      {collection.landing_body ? (
        <section className="servio-card">
          <span className="servio-eyebrow">О подборке</span>
          <div className="servio-product-richtext">
            {collection.landing_body.split(/\n+/).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}

      {relatedCollections.length ? (
        <section className="servio-discovery-section">
          <div className="servio-related__header">
            <span className="servio-eyebrow">Другие подборки</span>
            <h2 className="servio-card-title">Соседние collection surfaces</h2>
          </div>
          <div className="servio-discovery-grid servio-discovery-grid--spotlight">
            {relatedCollections.map((item) => (
              <DiscoveryEntityCard
                key={item.id}
                href={`/collections/${item.slug}`}
                kicker="Коллекция"
                title={item.hero_title || item.name}
                copy={pickText(
                  item.hero_text,
                  item.description,
                  "Соседняя подборка Servio для growth- и merchandising-сценариев.",
                )}
                cta="Открыть подборку"
                image={item.photo}
                imageAlt={item.name}
                meta={[item.products_count ? `${item.products_count} SKU` : "подборка Servio"]}
              />
            ))}
          </div>
        </section>
      ) : null}

      {collection.faq_body ? (
        <section className="servio-card">
          <span className="servio-eyebrow">FAQ</span>
          <h2 className="servio-card-title">{collection.faq_title || `FAQ по подборке ${collection.name}`}</h2>
          <div className="servio-product-richtext">
            {collection.faq_body.split(/\n+/).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
