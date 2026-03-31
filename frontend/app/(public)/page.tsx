import Link from "next/link";
import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Chip } from "@/components/ui/chip";
import { getBrands, getCategories, getCollections } from "@/lib/catalog-api";

export const metadata: Metadata = {
  title: "Servio | Товары для HoReCa",
  description:
    "Профессиональные товары для HoReCa в каталоге Servio: посуда, стекло, барный инвентарь, упаковка, текстиль и расходные материалы от проверенных поставщиков.",
};

const trustPoints = [
  {
    icon: "✓",
    title: "Проверенные поставщики",
    body: "Работаем только с верифицированными поставщиками на контракте.",
  },
  {
    icon: "→",
    title: "Доставка по России",
    body: "Доставляем в рестораны, кафе, отели и корпоративные кухни.",
  },
  {
    icon: "↻",
    title: "Повторные заказы",
    body: "История заказов и быстрый реордер для постоянных клиентов.",
  },
  {
    icon: "B2B",
    title: "Счёт и документы",
    body: "Работаем с юрлицами: счёт, накладная, договор поставки.",
  },
];

const heroQuickLinks = [
  { label: "Новинки", href: "/catalog?is_new=true" },
  { label: "Акции", href: "/catalog?is_promo=true" },
  { label: "Бренды", href: "/brands" },
  { label: "Коллекции", href: "/collections" },
];

export default async function HomePage() {
  const [categoriesResult, brandsResult, collectionsResult] = await Promise.allSettled([
    getCategories(),
    getBrands(),
    getCollections(),
  ]);

  const rootCategories =
    categoriesResult.status === "fulfilled"
      ? categoriesResult.value.filter((c) => c.parent === null).slice(0, 8)
      : [];

  const featuredBrands =
    brandsResult.status === "fulfilled" ? brandsResult.value.slice(0, 6) : [];

  const featuredCollections =
    collectionsResult.status === "fulfilled"
      ? collectionsResult.value.filter((c) => c.is_active && c.is_featured).slice(0, 3)
      : [];

  return (
    <div className="home-page">

      {/* 1. Hero */}
      <section className="home-hero" aria-label="Поиск товаров">
        <div className="home-hero__content">
          <p className="home-hero__eyebrow">Маркетплейс для HoReCa и корпоративных кухонь</p>
          <h1 className="home-hero__title">
            Всё для кухни, бара<br />и сервиса — в одном каталоге
          </h1>
          <p className="home-hero__lead">
            Посуда, стекло, барный инвентарь, упаковка, текстиль и расходные материалы
            от проверенных поставщиков.
          </p>

          <Link href="/search" className="home-hero__search-link" aria-label="Перейти к поиску">
            <span className="home-hero__search-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <circle cx="8.5" cy="8.5" r="5.75" stroke="currentColor" strokeWidth="1.6" />
                <path d="M13 13L17 17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </span>
            <span className="home-hero__search-placeholder">Найти товар, бренд или категорию…</span>
            <span className="home-hero__search-btn" aria-hidden="true">Найти</span>
          </Link>

          <div className="home-hero__actions">
            <Button href="/catalog" variant="primary" size="lg">Открыть каталог</Button>
            <Button href="/brands" variant="secondary" size="lg">Бренды</Button>
          </div>

          <div className="home-hero__quick" aria-label="Быстрые разделы">
            {heroQuickLinks.map((link) => (
              <Chip key={link.href} href={link.href}>{link.label}</Chip>
            ))}
          </div>
        </div>
      </section>

      {/* 2. Категории */}
      {rootCategories.length > 0 && (
        <section className="home-section" aria-labelledby="home-cats-heading">
          <div className="home-section__header">
            <h2 id="home-cats-heading" className="home-section__title">Категории товаров</h2>
            <Button href="/catalog" variant="ghost" size="sm">Весь каталог</Button>
          </div>
          <div className="home-cats-grid">
            {rootCategories.map((category) => (
              <Link
                key={category.id}
                href={`/catalog?category=${category.id}`}
                className="home-cat-card"
                aria-label={category.name}
              >
                {category.photo ? (
                  <div className="home-cat-card__media">
                    <img src={category.photo} alt={category.name} className="home-cat-card__image" loading="lazy" />
                  </div>
                ) : (
                  <div className="home-cat-card__media home-cat-card__media--empty" aria-hidden="true">
                    <span>{category.name.charAt(0)}</span>
                  </div>
                )}
                <div className="home-cat-card__body">
                  <strong className="home-cat-card__name">{category.name}</strong>
                  {category.product_count != null && (
                    <span className="home-cat-card__count">{category.product_count} позиций</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* 3. Коллекции */}
      {featuredCollections.length > 0 && (
        <section className="home-section" aria-labelledby="home-colls-heading">
          <div className="home-section__header">
            <h2 id="home-colls-heading" className="home-section__title">Подборки для закупки</h2>
            <Button href="/collections" variant="ghost" size="sm">Все подборки</Button>
          </div>
          <div className="home-colls-grid">
            {featuredCollections.map((collection) => (
              <Link
                key={collection.id}
                href={`/collections/${collection.slug}`}
                className="home-coll-card"
                aria-label={collection.name}
              >
                <div className={collection.photo ? "home-coll-card__media" : "home-coll-card__media home-coll-card__media--empty"}>
                  {collection.photo && (
                    <img src={collection.photo} alt={collection.name} className="home-coll-card__image" loading="lazy" />
                  )}
                </div>
                <div className="home-coll-card__body">
                  <Badge variant="default">Подборка</Badge>
                  <strong className="home-coll-card__name">{collection.name}</strong>
                  {collection.description && (
                    <p className="home-coll-card__desc">{collection.description}</p>
                  )}
                  {collection.products_count != null && (
                    <span className="home-coll-card__count">{collection.products_count} товаров</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* 4. Бренды */}
      {featuredBrands.length > 0 && (
        <section className="home-section" aria-labelledby="home-brands-heading">
          <div className="home-section__header">
            <h2 id="home-brands-heading" className="home-section__title">Бренды</h2>
            <Button href="/brands" variant="ghost" size="sm">Все бренды</Button>
          </div>
          <div className="home-brands-grid">
            {featuredBrands.map((brand) => (
              <Link
                key={brand.id}
                href={brand.slug ? `/brands/${brand.slug}` : `/catalog?brand=${brand.id}`}
                className="home-brand-card"
                aria-label={brand.name}
              >
                {brand.photo ? (
                  <img src={brand.photo} alt={brand.name} className="home-brand-card__logo" loading="lazy" />
                ) : (
                  <span className="home-brand-card__name">{brand.name}</span>
                )}
                {brand.products_count != null && (
                  <span className="home-brand-card__count">{brand.products_count} позиций</span>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* 5. Trust */}
      <section className="home-trust" aria-labelledby="home-trust-heading">
        <h2 id="home-trust-heading" className="home-section__title home-trust__title">Почему Servio</h2>
        <div className="home-trust-grid">
          {trustPoints.map((point) => (
            <div key={point.title} className="home-trust-card">
              <span className="home-trust-card__icon" aria-hidden="true">{point.icon}</span>
              <div className="home-trust-card__body">
                <strong className="home-trust-card__title">{point.title}</strong>
                <p className="home-trust-card__text">{point.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 6. CTA */}
      <section className="home-cta" aria-label="Начать закупку">
        <div className="home-cta__content">
          <h2 className="home-cta__title">Готовы начать закупку?</h2>
          <p className="home-cta__lead">
            Откройте каталог, выберите нужное и оформите заказ — или свяжитесь с нами,
            чтобы обсудить условия для вашего заведения.
          </p>
          <div className="home-cta__actions">
            <Button href="/catalog" variant="primary" size="lg">Открыть каталог</Button>
            <Button href="/search" variant="secondary" size="lg">Поиск по каталогу</Button>
          </div>
        </div>
      </section>

    </div>
  );
}
