import Image from "next/image";
import Link from "next/link";

import { formatPrice, getPrimaryImage, normalizeAssetUrl, type Product } from "@/lib/catalog-api";

type ProductCardProps = {
  product: Product;
};

export function ProductCard({ product }: ProductCardProps) {
  const image = getPrimaryImage(product);
  const imageUrl = normalizeAssetUrl(image?.url);
  const imageAlt = image?.alt || product.name;
  const inStock = product.stock_qty > 0;
  const brandHref = product.brand?.slug
    ? `/brands/${product.brand.slug}`
    : `/catalog?brand=${product.brand?.id}`;

  return (
    <article className="ui-pc">
      <Link href={`/products/${product.slug}`} className="ui-pc__media" tabIndex={-1} aria-hidden>
        <Image
          src={imageUrl}
          alt={imageAlt}
          fill
          sizes="(max-width: 480px) 100vw, (max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
          className="ui-pc__img"
        />
        {(product.is_new || product.is_promo) && (
          <div className="ui-pc__flags">
            {product.is_new && <span className="ui-badge ui-badge--default">Новинка</span>}
            {product.is_promo && <span className="ui-badge ui-badge--warning">Акция</span>}
          </div>
        )}
      </Link>

      <div className="ui-pc__body">
        <div className="ui-pc__meta">
          {product.brand ? (
            <Link href={brandHref} className="ui-pc__brand">
              {product.brand.name}
            </Link>
          ) : (
            <span className="ui-pc__brand">Servio</span>
          )}
          {inStock ? (
            <span className="ui-badge ui-badge--success">В наличии</span>
          ) : (
            <span className="ui-badge ui-badge--neutral">Под заказ</span>
          )}
        </div>

        <Link href={`/products/${product.slug}`} className="ui-pc__name-link">
          <h2 className="ui-pc__name">{product.name}</h2>
        </Link>

        <div className="ui-pc__footer">
          <span className="ui-pc__price">{formatPrice(product.price)}</span>
          <Link
            href={`/products/${product.slug}`}
            className={inStock ? "ui-btn ui-btn--primary ui-btn--sm" : "ui-btn ui-btn--secondary ui-btn--sm"}
          >
            {inStock ? "В корзину" : "Запросить"}
          </Link>
        </div>
      </div>
    </article>
  );
}
