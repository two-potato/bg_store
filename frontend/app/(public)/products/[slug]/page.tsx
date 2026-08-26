import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { ProductCard } from "@/components/product-card";
import {
  formatPrice,
  getPrimaryImage,
  getProductBySlug,
  getRelatedProducts,
  normalizeAssetUrl,
  normalizeSlugPath,
  productDimensionEntries,
} from "@/lib/catalog-api";

export const dynamic = "force-dynamic";

type ProductPageProps = {
  params: Promise<{ slug: string }>;
};

function sanitizeMetaDescription(value: string | undefined) {
  if (!value) {
    return "Карточка товара в новом storefront-контуре Servio.";
  }

  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= 190) {
    return normalized;
  }
  return `${normalized.slice(0, 187).trimEnd()}...`;
}

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProductBySlug(slug);

  if (!product) {
    return {
      title: "Товар не найден",
    };
  }

  return {
    title: product.name,
    description: sanitizeMetaDescription(
      product.description ||
        product.purpose ||
        product.composition ||
        `Карточка товара ${product.name} в каталоге Servio.`,
    ),
  };
}

const serviceHighlights = [
  {
    title: "Подбор по задаче",
    copy: "Помогаем собрать ассортимент под формат заведения, меню и операционную нагрузку.",
  },
  {
    title: "Коммерческое предложение",
    copy: "Для объёмных закупок и корпоративных клиентов готовим отдельные условия и сопровождение.",
  },
  {
    title: "Поставка и повторный заказ",
    copy: "Поддерживаем регулярное снабжение и быстрый возврат к уже проверенным позициям.",
  },
];

export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);

  if (!product) {
    notFound();
  }

  const relatedProducts = await getRelatedProducts(product, 4);
  const primaryImage = getPrimaryImage(product);
  const dimensionEntries = productDimensionEntries(product);
  const attributeEntries = Object.entries(product.attributes || {}).filter(([, value]) => Boolean(value));
  const stockLabel = product.stock_qty > 0 ? `${product.stock_qty} шт. в наличии` : "Под заказ";
  const stockTone = product.stock_qty > 0 ? "servio-stock-badge--ok" : "servio-stock-badge--empty";
  const leadTime = product.lead_time_days && product.lead_time_days > 0 ? `${product.lead_time_days} рабочих дн.` : "1-3 рабочих дня";
  const brandHref = product.brand?.slug ? `/brands/${product.brand.slug}` : product.brand?.id ? `/catalog?brand=${product.brand.id}` : "/catalog";
  const categoryHref = product.category_detail?.full_slug_path
    ? `/categories/${normalizeSlugPath(product.category_detail.full_slug_path)}`
    : product.category_detail?.id
      ? `/catalog?category=${product.category_detail.id}`
      : "/catalog";

  return (
    <div className="servio-product-page">
      <nav className="servio-breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Главная</Link>
        <span>/</span>
        <Link href="/catalog">Каталог</Link>
        {product.category_detail ? (
          <>
            <span>/</span>
            <Link href={categoryHref}>{product.category_detail.name}</Link>
          </>
        ) : null}
        <span>/</span>
        <span>{product.name}</span>
      </nav>

      <section className="servio-product-layout">
        <article className="servio-card servio-product-gallery">
          <div className="servio-product-gallery__stage">
            <img
              src={normalizeAssetUrl(primaryImage?.url)}
              alt={primaryImage?.alt || product.name}
              className="servio-product-gallery__image"
            />
            <div className="servio-product-gallery__badges">
              {product.is_new ? <span className="servio-badge servio-badge--accent">Новинка</span> : null}
              {product.is_promo ? <span className="servio-badge servio-badge--violet">Акция</span> : null}
            </div>
          </div>

          {product.images.length > 1 ? (
            <div className="servio-product-gallery__thumbs">
              {product.images.map((image) => (
                <div key={`${image.url}-${image.ordering}`} className="servio-product-gallery__thumb">
                  <img src={normalizeAssetUrl(image.url)} alt={image.alt || product.name} />
                </div>
              ))}
            </div>
          ) : null}
        </article>

        <aside className="servio-card servio-card--hero servio-product-summary">
          <div className="servio-product-summary__header">
            <span className="servio-eyebrow">Карточка товара</span>
            <div className="servio-product-summary__links">
              {product.brand ? (
                <Link href={brandHref} className="servio-inline-link">
                  {product.brand.name}
                </Link>
              ) : null}
              {product.series ? (
                <Link href={`/catalog?series=${product.series.id}`} className="servio-inline-link">
                  {product.series.name}
                </Link>
              ) : null}
            </div>
          </div>

          <h1 className="servio-page-title">{product.name}</h1>
          <p className="servio-copy servio-copy--lead">
            {product.description || product.purpose || "Карточка товара собрана поверх существующего backend-контракта и сохраняет старый брендовый характер Servio."}
          </p>

          <div className="servio-product-summary__price">
            <strong>{formatPrice(product.price)}</strong>
            <span className={`servio-stock-badge ${stockTone}`}>{stockLabel}</span>
          </div>

          <div className="servio-product-summary__grid">
            <div className="servio-product-summary__item">
              <span>SKU</span>
              <strong>{product.sku}</strong>
            </div>
            <div className="servio-product-summary__item">
              <span>Минимальный заказ</span>
              <strong>
                {product.min_order_qty || 1} {product.unit}
              </strong>
            </div>
            <div className="servio-product-summary__item">
              <span>Срок поставки</span>
              <strong>{leadTime}</strong>
            </div>
            <div className="servio-product-summary__item">
              <span>Поставщик</span>
              <strong>{product.seller || "Сеть поставщиков Servio"}</strong>
            </div>
          </div>

          <div className="servio-actions">
            <Link href={brandHref} className="servio-button servio-button--primary">
              Ещё товары бренда
            </Link>
            <Link href="/contacts" className="servio-button servio-button--secondary">
              Запросить предложение
            </Link>
          </div>

          <div className="servio-product-note">
            По этой позиции можно быстро перейти к подбору аналога, запросу предложения и дальнейшему согласованию
            заказа с командой Servio.
          </div>

          {product.tags.length ? (
            <div className="servio-product-tags">
              {product.tags.slice(0, 6).map((tag) => (
                <span key={tag.id} className="servio-filter-chip">
                  {tag.name}
                </span>
              ))}
            </div>
          ) : null}
        </aside>
      </section>

      <section className="servio-product-columns">
        <article className="servio-card">
          <span className="servio-eyebrow">Описание</span>
          <h2 className="servio-card-title">Что важно знать по позиции</h2>
          <div className="servio-product-richtext">
            {product.composition ? <p>{product.composition}</p> : null}
            {product.flavor ? <p>Вкусовой профиль: {product.flavor}</p> : null}
            {product.shelf_life ? <p>Срок хранения: {product.shelf_life}</p> : null}
            {product.country_of_origin ? <p>Страна происхождения: {product.country_of_origin}</p> : null}
            {!product.composition && !product.flavor && !product.shelf_life ? (
              <p>Детальное описание для этой позиции будет расширяться по мере развития storefront data layer.</p>
            ) : null}
          </div>
        </article>

        <article className="servio-card">
          <span className="servio-eyebrow">Характеристики</span>
          <h2 className="servio-card-title">Спецификация товара</h2>
          <div className="servio-spec-grid">
            {dimensionEntries.map((entry) => (
              <div key={entry.label} className="servio-spec-item">
                <span>{entry.label}</span>
                <strong>{entry.value}</strong>
              </div>
            ))}
            <div className="servio-spec-item">
              <span>Артикул производителя</span>
              <strong>{product.manufacturer_sku || "Уточняется"}</strong>
            </div>
            <div className="servio-spec-item">
              <span>Упаковка</span>
              <strong>
                {product.pack_qty} {product.unit}
              </strong>
            </div>
          </div>

          {attributeEntries.length ? (
            <div className="servio-attribute-list">
              {attributeEntries.map(([label, value]) => (
                <div key={label} className="servio-attribute-list__item">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      </section>

      <section className="servio-service-grid" aria-label="Сервисные возможности Servio">
        {serviceHighlights.map((item) => (
          <article key={item.title} className="servio-card servio-service-card">
            <span className="servio-eyebrow">Сервис Servio</span>
            <h2 className="servio-card-title">{item.title}</h2>
            <p className="servio-copy">{item.copy}</p>
          </article>
        ))}
      </section>

      {relatedProducts.length ? (
        <section className="servio-product-related">
          <div className="servio-related__header">
            <span className="servio-eyebrow">Похожие товары</span>
            <h2 className="servio-card-title">Похожие позиции</h2>
          </div>
          <div className="servio-product-grid">
            {relatedProducts.map((item) => (
              <ProductCard key={item.id} product={item} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
