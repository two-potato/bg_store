import Link from "next/link";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { getBrands, getCollections, pickText } from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Бренды",
  description:
    "Брендовые витрины Servio в новом storefront-контуре: поставщики, продуктовые линии и быстрый вход в ассортимент.",
};

export default async function BrandsPage() {
  const [brands, collections] = await Promise.all([getBrands(), getCollections()]);
  const totalProducts = brands.reduce((sum, brand) => sum + (brand.products_count || 0), 0);
  const featuredCollections = collections.filter((collection) => collection.is_featured).slice(0, 3);

  return (
    <div className="servio-discovery-page">
      <section className="servio-discovery-hero servio-card servio-card--hero">
        <div className="servio-discovery-hero__content">
          <span className="servio-eyebrow">Brand showcase</span>
          <p className="servio-kicker">Бренды и торговые линии Servio</p>
          <h1 className="servio-page-title">Открывайте ассортимент по бренду, а не через шумный общий каталог</h1>
          <p className="servio-copy servio-copy--lead">
            В новой discovery wave бренды стали отдельными SEO- и UX-поверхностями: проще зайти в нужную марку,
            увидеть покрытие по категориям и быстро перейти в карточки товара.
          </p>
          <div className="servio-chip-row">
            <span className="servio-chip">брендовые страницы на Next</span>
            <span className="servio-chip">same-origin SEO</span>
            <span className="servio-chip">backend как source of truth</span>
          </div>
          <div className="servio-actions">
            <Link href="/catalog" className="servio-button servio-button--primary">
              Открыть каталог
            </Link>
            <Link href="/collections" className="servio-button servio-button--secondary">
              Посмотреть подборки
            </Link>
          </div>
        </div>

        <aside className="servio-discovery-hero__rail">
          <div className="servio-catalog-stat">
            <strong>{brands.length}</strong>
            <span>брендов уже доступны в новом storefront</span>
          </div>
          <div className="servio-catalog-stat">
            <strong>{totalProducts}</strong>
            <span>SKU объединены в brand-entry surfaces</span>
          </div>
          <div className="servio-catalog-stat">
            <strong>{featuredCollections.length}</strong>
            <span>рекламных подборки усиливают discovery-сценарии</span>
          </div>
        </aside>
      </section>

      {featuredCollections.length ? (
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
                "Подборка Servio для быстрого входа в сценарий закупки.",
              )}
              cta="Открыть подборку"
              image={collection.photo}
              imageAlt={collection.name}
              meta={[
                collection.products_count ? `${collection.products_count} SKU` : "Кураторская подборка",
                collection.is_featured ? "featured placement" : "merchanting surface",
              ]}
            />
          ))}
        </section>
      ) : null}

      <section className="servio-discovery-section">
        <div className="servio-related__header">
          <span className="servio-eyebrow">Все бренды</span>
          <h2 className="servio-card-title">Brand-first navigation для закупок и repeat purchase</h2>
        </div>

        {brands.length ? (
          <div className="servio-discovery-grid">
            {brands.map((brand) => (
              <DiscoveryEntityCard
                key={brand.id}
                href={`/brands/${brand.slug}`}
                kicker="Бренд"
                title={brand.name}
                copy={pickText(
                  brand.description,
                  brand.landing_body,
                  "Бренд представлен в профессиональном каталоге Servio и готов к data-driven витрине.",
                )}
                cta="Открыть бренд"
                image={brand.photo}
                imageAlt={brand.name}
                imageFit="contain"
                fallback={brand.name}
                meta={[
                  brand.products_count ? `${brand.products_count} SKU` : "SKU уточняются",
                  brand.categories_count ? `${brand.categories_count} категорий` : "категории в каталоге",
                  brand.collections_count ? `${brand.collections_count} коллекций` : "подборки и промо",
                ]}
              />
            ))}
          </div>
        ) : (
          <section className="servio-card servio-empty-state">
            <span className="servio-eyebrow">Пустая выдача</span>
            <h2 className="servio-card-title">Бренды пока не опубликованы</h2>
            <p className="servio-copy">
              Discovery shell уже готов, поэтому следующая публикация брендов появится в той же UX-системе без новой
              переделки storefront.
            </p>
          </section>
        )}
      </section>
    </div>
  );
}
