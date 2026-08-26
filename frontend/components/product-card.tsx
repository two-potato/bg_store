import Link from "next/link";

import {
  formatPrice,
  getPrimaryImage,
  normalizeAssetUrl,
  productFactList,
  type Product,
} from "@/lib/catalog-api";

type ProductCardProps = {
  product: Product;
};

export function ProductCard({ product }: ProductCardProps) {
  const image = getPrimaryImage(product);
  const facts = productFactList(product).slice(0, 3);
  const stockLabel = product.stock_qty > 0 ? `${product.stock_qty} шт. в наличии` : "Под заказ";
  const stockTone = product.stock_qty > 0 ? "servio-stock-badge--ok" : "servio-stock-badge--empty";
  const leadTime = product.lead_time_days && product.lead_time_days > 0 ? `${product.lead_time_days} дн.` : "1-3 дн.";
  const minOrder = `${product.min_order_qty || 1} ${product.unit}`;
  const brandHref = product.brand?.slug ? `/brands/${product.brand.slug}` : product.brand?.id ? `/catalog?brand=${product.brand.id}` : "/catalog";

  return (
    <article className="servio-product-card">
      <Link href={`/products/${product.slug}`} className="servio-product-card__media">
        <img
          src={normalizeAssetUrl(image?.url)}
          alt={image?.alt || product.name}
          loading="lazy"
          className="servio-product-card__image"
        />
        <div className="servio-product-card__badges">
          {product.is_new ? <span className="servio-badge servio-badge--accent">Новинка</span> : null}
          {product.is_promo ? <span className="servio-badge servio-badge--violet">Акция</span> : null}
        </div>
      </Link>

      <div className="servio-product-card__body">
        <div className="servio-product-card__topline">
          {product.brand ? (
            <Link href={brandHref} className="servio-product-card__brand">
              {product.brand.name}
            </Link>
          ) : (
            <span className="servio-product-card__brand">Подборка Servio</span>
          )}
          <span className={`servio-stock-badge ${stockTone}`}>{stockLabel}</span>
        </div>

        <Link href={`/products/${product.slug}`} className="servio-product-card__title-link">
          <h2 className="servio-product-card__title">{product.name}</h2>
        </Link>

        <div className="servio-product-card__meta">
          <span>SKU {product.sku}</span>
          <span>MOQ {minOrder}</span>
          <span>Срок поставки {leadTime}</span>
        </div>

        <p className="servio-product-card__purpose">
          {product.purpose || product.description || "Позиция для устойчивой HoReCa-подачи и повседневной эксплуатации."}
        </p>

        {facts.length ? (
          <ul className="servio-product-card__facts">
            {facts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
        ) : null}

        <div className="servio-product-card__footer">
          <div>
            <div className="servio-product-card__price">{formatPrice(product.price)}</div>
            <div className="servio-product-card__seller">
              Поставщик: <strong>{product.seller || "Сеть поставщиков Servio"}</strong>
            </div>
          </div>
          <Link href={`/products/${product.slug}`} className="servio-button servio-button--secondary">
            Открыть карточку
          </Link>
        </div>
      </div>
    </article>
  );
}
