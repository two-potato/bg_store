 import Link from "next/link";

 import { CatalogAddToCart } from "@/components/catalog/catalog-add-to-cart";
 import { formatPrice, getPrimaryImage, normalizeAssetUrl, type Product } from "@/lib/catalog-api";

type CatalogProductCardProps = {
  product: Product;
  variant: "a" | "b" | "c" | "d";
  csrfToken: string;
  cartUrl: string;
  initialQty?: number;
};

 function parseNumber(value: string | number | undefined | null) {
   if (value === undefined || value === null) {
     return null;
   }
   const parsed = Number(value);
   if (!Number.isFinite(parsed)) {
     return null;
   }
   return parsed;
 }

 function getRating(product: Product) {
   const ratingValue =
     parseNumber(product.attributes?.rating_avg) ??
     parseNumber(product.attributes?.rating) ??
     parseNumber(product.attributes?.rating_value);
   const ratingCount =
     parseNumber(product.attributes?.rating_count) ??
     parseNumber(product.attributes?.reviews_count) ??
     parseNumber(product.attributes?.review_count);
 
   return {
     value: ratingValue ?? 0,
     count: ratingCount ?? 0,
   };
 }

 export function CatalogProductCard({
   product,
   variant,
   csrfToken,
   cartUrl,
   initialQty = 0,
 }: CatalogProductCardProps) {
   const image = getPrimaryImage(product);
   const stockLabel = product.stock_qty > 0 ? `${product.stock_qty} шт. в наличии` : "Под заказ";
   const rating = getRating(product);
   const minOrder = product.min_order_qty || 1;
 
   return (
     <article className={`market-product-card market-product-card--${variant}`}>
       <Link href={`/products/${product.slug}`} className="market-product-card__media">
         <img
           src={normalizeAssetUrl(image?.url)}
           alt={image?.alt || product.name}
           loading="lazy"
           className="market-product-card__image"
         />
         <div className="market-product-card__badges">
           {product.is_promo ? <span className="market-badge market-badge--promo">Скидка</span> : null}
           {product.is_new ? <span className="market-badge market-badge--new">Новинка</span> : null}
         </div>
       </Link>
 
       <div className="market-product-card__body">
         <div className="market-product-card__meta">
           <span className="market-product-card__brand">{product.brand?.name || "Servio"}</span>
           <span className={`market-stock ${product.stock_qty > 0 ? "is-available" : "is-pending"}`}>
             {stockLabel}
           </span>
         </div>
 
         <Link href={`/products/${product.slug}`} className="market-product-card__title">
           {product.name}
         </Link>
 
         <div className="market-product-card__rating" aria-label="Рейтинг товара">
           <span className="market-rating__value">{rating.value ? rating.value.toFixed(1) : "—"}</span>
           <span className="market-rating__count">
             {rating.count > 0 ? `${rating.count} отзывов` : "Нет отзывов"}
           </span>
         </div>
 
         <div className="market-product-card__price">
           <span>{formatPrice(product.price)}</span>
           <span className="market-product-card__unit">за {product.unit || "шт."}</span>
         </div>
 
         <div className="market-product-card__actions">
          <CatalogAddToCart
            productId={product.id}
            minQty={minOrder}
            csrfToken={csrfToken}
            initialQty={initialQty}
            compact={variant === "c" || variant === "d"}
            cartUrl={cartUrl}
          />
         </div>
       </div>
     </article>
   );
 }
