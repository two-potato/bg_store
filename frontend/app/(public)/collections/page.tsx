import Link from "next/link";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { getBrands, getCollections, pickText } from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Коллекции",
  description:
    "Коллекции и подборки Servio: merchandising-ready surfaces для repeat purchase, запусков и быстрых сценариев закупки.",
};

export default async function CollectionsPage() {
  const [collections, brands] = await Promise.all([getCollections(), getBrands()]);
  const featuredBrands = brands.slice(0, 4);

  return (
    <div className="servio-discovery-page">
      <section className="servio-discovery-hero servio-card servio-card--hero">
        <div className="servio-discovery-hero__content">
          <span className="servio-eyebrow">Collections</span>
          <p className="servio-kicker">Сценарные подборки Servio</p>
          <h1 className="servio-page-title">Кураторские наборы под открытие, сезон и повторные закупки</h1>
          <p className="servio-copy servio-copy--lead">
            Коллекции стали отдельным discovery-layer: можно заходить не только по товару или бренду, но и по
            коммерческому сценарию, который уже упакован в знакомую сервийную подачу.
          </p>
          <div className="servio-actions">
            <Link href="/catalog" className="servio-button servio-button--primary">
              Перейти в каталог
            </Link>
            <Link href="/brands" className="servio-button servio-button--secondary">
              Открыть бренды
            </Link>
          </div>
        </div>

        <aside className="servio-discovery-hero__rail">
          <div className="servio-catalog-stat">
            <strong>{collections.length}</strong>
            <span>активных подборок доступны в storefront</span>
          </div>
          <div className="servio-catalog-stat">
            <strong>{collections.filter((item) => item.is_featured).length}</strong>
            <span>featured-блоков можно использовать в growth и SEO</span>
          </div>
          <div className="servio-catalog-stat">
            <strong>{featuredBrands.length}</strong>
            <span>брендов подсвечивают новые merchandised surfaces</span>
          </div>
        </aside>
      </section>

      {collections.length ? (
        <section className="servio-discovery-section">
          <div className="servio-related__header">
            <span className="servio-eyebrow">Все подборки</span>
            <h2 className="servio-card-title">Collection-first surfaces для B2B и B2C discovery</h2>
          </div>
          <div className="servio-discovery-grid">
            {collections.map((collection) => (
              <DiscoveryEntityCard
                key={collection.id}
                href={`/collections/${collection.slug}`}
                kicker={collection.is_featured ? "Featured collection" : "Коллекция"}
                title={collection.hero_title || collection.name}
                copy={pickText(
                  collection.hero_text,
                  collection.description,
                  "Подборка Servio для навигации по готовому сценарию закупки.",
                )}
                cta="Открыть коллекцию"
                image={collection.photo}
                imageAlt={collection.name}
                meta={[
                  collection.products_count ? `${collection.products_count} SKU` : "SKU уточняются",
                  collection.is_featured ? "мерчандайзинговый приоритет" : "сценарная подборка",
                ]}
              />
            ))}
          </div>
        </section>
      ) : (
        <section className="servio-card servio-empty-state">
          <span className="servio-eyebrow">Пустая выдача</span>
          <h2 className="servio-card-title">Коллекции пока не опубликованы</h2>
          <p className="servio-copy">
            Слой для merchandising surfaces уже готов. Следующие коллекции смогут выехать на новый storefront без
            дополнительной миграции UI.
          </p>
        </section>
      )}
    </div>
  );
}
