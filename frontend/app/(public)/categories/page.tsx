import Link from "next/link";
import type { Metadata } from "next";

import { DiscoveryEntityCard } from "@/components/discovery-entity-card";
import { getCategories, getCollections, pickText } from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Категории",
  description:
    "Категорийные landing pages Servio для long-tail SEO, навигации по ассортименту и быстрого перехода к нужному типу товара.",
};

export default async function CategoriesPage() {
  const [categories, collections] = await Promise.all([getCategories(), getCollections()]);
  const rootCategories = categories.filter((category) => category.parent === null).slice(0, 12);
  const featuredCollections = collections.filter((collection) => collection.is_featured).slice(0, 3);

  return (
    <div className="servio-discovery-page">
      <section className="servio-discovery-hero servio-card servio-card--hero">
        <div className="servio-discovery-hero__content">
          <span className="servio-eyebrow">Category landing</span>
          <p className="servio-kicker">Категории Servio</p>
          <h1 className="servio-page-title">Long-tail SEO и быстрый вход в ассортимент по рабочим направлениям</h1>
          <p className="servio-copy servio-copy--lead">
            Категорийные страницы помогают заходить в каталог по понятным задачам кухни, сервиса, бара и
            операционной закупки. Это уже отдельные Next surfaces, а не только фильтр внутри старого HTML-каталога.
          </p>
          <div className="servio-actions">
            <Link href="/catalog" className="servio-button servio-button--primary">
              Открыть общий каталог
            </Link>
            <Link href="/search" className="servio-button servio-button--secondary">
              Перейти к поиску
            </Link>
          </div>
        </div>

        <aside className="servio-discovery-hero__rail">
          <div className="servio-catalog-stat">
            <strong>{rootCategories.length}</strong>
            <span>корневых направлений уже доступны в storefront</span>
          </div>
          <div className="servio-catalog-stat">
            <strong>{categories.length}</strong>
            <span>категорий можно разворачивать в SEO- и discovery-цепочки</span>
          </div>
          <div className="servio-catalog-stat">
            <strong>{featuredCollections.length}</strong>
            <span>подборки помогают усиливать категории рекламными блоками</span>
          </div>
        </aside>
      </section>

      {rootCategories.length ? (
        <section className="servio-discovery-section">
          <div className="servio-related__header">
            <span className="servio-eyebrow">Корневые направления</span>
            <h2 className="servio-card-title">Категории как самостоятельные SEO и discovery surfaces</h2>
          </div>
          <div className="servio-discovery-grid">
            {rootCategories.map((category) => (
              <DiscoveryEntityCard
                key={category.id}
                href={`/categories/${category.full_slug_path || category.slug}`}
                kicker="Категория"
                title={category.hero_title || category.name}
                copy={pickText(
                  category.hero_text,
                  category.description,
                  "Категорийная витрина Servio для профессиональных закупок и long-tail discovery.",
                )}
                cta="Открыть категорию"
                image={category.photo}
                imageAlt={category.name}
                meta={[
                  category.product_count ? `${category.product_count} SKU` : "ассортимент Servio",
                  "SEO-ready route",
                ]}
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
