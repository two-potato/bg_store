 "use client";

 import { useState } from "react";

 import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";

 type CatalogAddToCartProps = {
   productId: number;
   minQty: number;
   csrfToken: string;
   initialQty?: number;
   compact?: boolean;
   cartUrl: string;
 };

 type CartMutationResponse = {
   ok: boolean;
   error?: string;
   cart: {
     items: Array<{ product: { id: number }; qty: number }>;
     cart_count: number;
     total: string;
   };
 };

 function clampQty(value: number, minQty: number) {
   if (!Number.isFinite(value)) {
     return minQty;
   }
   return Math.max(minQty, Math.floor(value));
 }

 export function CatalogAddToCart({
   productId,
   minQty,
   csrfToken,
   initialQty = 0,
   compact = false,
   cartUrl,
 }: CatalogAddToCartProps) {
   const [qty, setQty] = useState(initialQty);
   const [pending, setPending] = useState(false);
   const [error, setError] = useState("");
 
   async function mutateCart(
     path: "/api/storefront/cart/add/" | "/api/storefront/cart/update/" | "/api/storefront/cart/remove/",
     body: Record<string, unknown>,
     event?: "cart_qty_incremented" | "cart_qty_decremented",
   ) {
     setPending(true);
     setError("");
 
     try {
       const response = await fetch(path, {
         method: "POST",
         credentials: "include",
         headers: {
           accept: "application/json",
           "content-type": "application/json",
           "x-csrftoken": csrfToken,
           "x-requested-with": "XMLHttpRequest",
         },
         body: JSON.stringify(body),
       });
 
       const result = (await response.json()) as CartMutationResponse;
       if (!response.ok || !result.ok) {
         setError(result.error || "Не удалось добавить товар.");
         return;
       }
 
       const line = result.cart.items.find((item) => item.product.id === productId);
       setQty(line ? line.qty : 0);
       if (event) {
         void trackBuyerWaveEvent(event, "catalog", { product_id: productId });
       }
     } catch {
       setError("Ошибка сети. Повторите попытку.");
     } finally {
       setPending(false);
     }
   }
 
   async function handleAdd() {
     await mutateCart("/api/storefront/cart/add/", { product_id: productId, qty: minQty }, "cart_qty_incremented");
   }
 
   async function handleIncrease() {
     const nextQty = clampQty(qty + 1, minQty);
     await mutateCart(
       "/api/storefront/cart/update/",
       { product_id: productId, op: "set", qty: nextQty },
       "cart_qty_incremented",
     );
   }
 
   async function handleDecrease() {
     const nextQty = clampQty(qty - 1, minQty);
     if (nextQty <= 0 || nextQty < minQty) {
       await mutateCart("/api/storefront/cart/remove/", { product_id: productId }, "cart_qty_decremented");
       return;
     }
     await mutateCart(
       "/api/storefront/cart/update/",
       { product_id: productId, op: "set", qty: nextQty },
       "cart_qty_decremented",
     );
   }
 
   return (
     <div className={`market-cart-action ${compact ? "is-compact" : ""}`}>
       {qty > 0 ? (
         <>
           <div className="market-stepper" aria-label="Изменить количество">
             <button type="button" onClick={handleDecrease} disabled={pending} aria-label="Уменьшить количество">
               -
             </button>
             <span>{qty}</span>
             <button type="button" onClick={handleIncrease} disabled={pending} aria-label="Увеличить количество">
               +
             </button>
           </div>
           <a href={cartUrl} className="market-cart-link">
             В корзину
           </a>
         </>
       ) : (
         <button type="button" className="market-add-button" onClick={handleAdd} disabled={pending}>
           Добавить
         </button>
       )}
       {error ? <span className="market-cart-error">{error}</span> : null}
     </div>
   );
 }
