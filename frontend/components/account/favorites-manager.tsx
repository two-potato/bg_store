"use client";

import Link from "next/link";
import { useState } from "react";

import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";
import { formatPrice } from "@/lib/catalog-api";
import type { BridgeToolProduct } from "@/lib/buyer-account-api";

type FavoritesManagerProps = {
  initialFavorites: BridgeToolProduct[];
  csrfToken: string;
};

export function FavoritesManager({ initialFavorites, csrfToken }: FavoritesManagerProps) {
  const [favorites, setFavorites] = useState(initialFavorites);
  const [pendingProductId, setPendingProductId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function refreshFavorites() {
    const response = await fetch("/api/storefront/tools/favorites/", {
      method: "GET",
      credentials: "include",
      headers: { accept: "application/json" },
    });
    const payload = (await response.json()) as {
      ok: boolean;
      favorites: BridgeToolProduct[];
    };
    if (response.ok && payload.ok) {
      setFavorites(payload.favorites);
    }
  }

  async function toggleFavorite(productId: number) {
    setPendingProductId(productId);
    setError("");

    try {
      const response = await fetch("/api/storefront/tools/favorites/toggle/", {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({ product_id: productId }),
      });

      const payload = (await response.json()) as { ok: boolean; error?: string; favorited?: boolean };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось обновить избранное.");
        return;
      }

      void trackBuyerWaveEvent("favorite_toggled", "favorites", {
        product_id: productId,
        favorited: payload.favorited,
      });
      await refreshFavorites();
    } catch {
      setError("Сетевая ошибка при обновлении избранного.");
    } finally {
      setPendingProductId(null);
    }
  }

  if (!favorites.length) {
    return (
      <section className="servio-card servio-empty-state servio-card--soft">
        <h2 className="servio-card-title">Избранное пусто</h2>
        <p className="servio-copy">Добавляйте позиции в избранное из каталога, чтобы быстро возвращаться к ним.</p>
        <div className="servio-actions">
          <Link href="/catalog" className="servio-button servio-button--primary">
            Перейти в каталог
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="servio-card" aria-live="polite">
      <div className="servio-account-section-head">
        <h2 className="servio-card-title">Избранные товары</h2>
      </div>

      {error ? <p className="servio-cart-summary__error">{error}</p> : null}

      <div className="servio-account-order-list">
        {favorites.map((product) => (
          <article key={product.id} className="servio-account-order-row">
            <div className="servio-account-order-row__main">
              <strong>{product.name}</strong>
              <span>SKU {product.sku}</span>
              <span>{product.brand_name || "Без бренда"}</span>
            </div>
            <div className="servio-account-order-row__meta">
              <span className="servio-chip">{formatPrice(product.price)}</span>
              <span className="servio-chip">{product.stock_qty > 0 ? `${product.stock_qty} шт.` : "Под заказ"}</span>
              <Link href={`/products/${product.slug}`} className="servio-button servio-button--secondary">
                Открыть
              </Link>
              <button
                type="button"
                className="servio-button servio-button--ghost"
                onClick={() => toggleFavorite(product.id)}
                disabled={pendingProductId === product.id}
              >
                {pendingProductId === product.id ? "Обновляем..." : "Убрать"}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
