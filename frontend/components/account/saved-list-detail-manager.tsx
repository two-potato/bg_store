"use client";

import Link from "next/link";
import { useState } from "react";

import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";
import { formatPrice } from "@/lib/catalog-api";
import type { BridgeSavedListDetailResponse } from "@/lib/buyer-account-api";

type SavedListDetailManagerProps = {
  listId: number;
  initialDetail: BridgeSavedListDetailResponse["saved_list"];
  csrfToken: string;
};

export function SavedListDetailManager({
  listId,
  initialDetail,
  csrfToken,
}: SavedListDetailManagerProps) {
  const [detail, setDetail] = useState(initialDetail);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function refreshDetail() {
    const response = await fetch(`/api/storefront/tools/lists/${listId}/`, {
      method: "GET",
      credentials: "include",
      headers: { accept: "application/json" },
    });
    const payload = (await response.json()) as BridgeSavedListDetailResponse;
    if (response.ok && payload.ok) {
      setDetail(payload.saved_list);
    }
  }

  async function removeItem(itemId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/storefront/tools/lists/${listId}/remove-item/`, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({ item_id: itemId }),
      });
      const payload = (await response.json()) as { ok: boolean; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось удалить позицию.");
        return;
      }
      void trackBuyerWaveEvent("saved_list_item_removed", "saved_list_detail", {
        list_id: listId,
        item_id: itemId,
      });
      await refreshDetail();
      setSuccess("Позиция удалена из списка.");
    } catch {
      setError("Сетевая ошибка при удалении позиции.");
    } finally {
      setPending(false);
    }
  }

  async function moveToCart() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/storefront/tools/lists/${listId}/move-to-cart/`, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({}),
      });
      const payload = (await response.json()) as { ok: boolean; moved_items?: number; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось перенести список в корзину.");
        return;
      }
      void trackBuyerWaveEvent("saved_list_moved_to_cart", "saved_list_detail", {
        list_id: listId,
        moved_items: payload.moved_items || 0,
      });
      setSuccess(`В корзину добавлено позиций: ${payload.moved_items || 0}.`);
    } catch {
      setError("Сетевая ошибка при переносе в корзину.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="servio-card" aria-live="polite">
      <div className="servio-account-section-head">
        <h2 className="servio-card-title">{detail.name}</h2>
        <div className="servio-actions">
          <button type="button" className="servio-button servio-button--primary" onClick={moveToCart} disabled={pending}>
            {pending ? "Обновляем..." : "В корзину"}
          </button>
          <Link href="/account/lists" className="servio-button servio-button--secondary">
            Все списки
          </Link>
        </div>
      </div>

      <p className="servio-copy">{detail.description || "Без описания."}</p>

      {error ? <p className="servio-cart-summary__error">{error}</p> : null}
      {success ? <p className="servio-account-success">{success}</p> : null}

      {detail.items.length ? (
        <div className="servio-account-order-list">
          {detail.items.map((item) => (
            <article key={item.id} className="servio-account-order-row">
              <div className="servio-account-order-row__main">
                <strong>{item.product.name}</strong>
                <span>SKU {item.product.sku}</span>
                <span>{formatPrice(item.product.price)} × {item.quantity}</span>
              </div>
              <div className="servio-account-order-row__meta">
                <span className="servio-chip">{formatPrice(item.product.price)}</span>
                <Link href={`/products/${item.product.slug}`} className="servio-button servio-button--secondary">
                  Товар
                </Link>
                <button
                  type="button"
                  className="servio-button servio-button--ghost"
                  onClick={() => removeItem(item.id)}
                  disabled={pending}
                >
                  Удалить
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="servio-copy">Список пуст. Добавление товаров в список будет расширено в следующей итерации UX.</p>
      )}
    </section>
  );
}
