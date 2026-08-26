"use client";

import { useState } from "react";
import type { BridgeOrderReorderResponse } from "@/lib/buyer-account-api";
import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";

type OrderReorderActionProps = {
  orderId: number;
  csrfToken: string;
  reorderUrl: string;
  cartUrl: string;
};

function resultLabel(value: BridgeOrderReorderResponse["reorder"]["result_type"]) {
  if (value === "full") {
    return "Все позиции добавлены в корзину.";
  }
  if (value === "partial") {
    return "Часть позиций добавлена, часть скорректирована по остаткам.";
  }
  return "Позиции не удалось добавить в корзину.";
}

export function OrderReorderAction({
  orderId,
  csrfToken,
  reorderUrl,
  cartUrl,
}: OrderReorderActionProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BridgeOrderReorderResponse["reorder"] | null>(null);

  async function handleReorder() {
    setPending(true);
    setError("");
    void trackBuyerWaveEvent("order_reorder_clicked", "order_detail", {
      order_id: orderId,
    });

    try {
      const response = await fetch(reorderUrl, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({ order_id: orderId }),
      });

      const payload = (await response.json()) as BridgeOrderReorderResponse & { error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось выполнить повтор заказа.");
        return;
      }

      setResult(payload.reorder);
    } catch {
      setError("Сетевая ошибка при повторе заказа.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="servio-order-reorder" aria-live="polite">
      <button
        type="button"
        className="servio-button servio-button--primary"
        onClick={handleReorder}
        disabled={pending}
      >
        {pending ? "Добавляем в корзину..." : "Повторить заказ"}
      </button>

      {error ? <p className="servio-cart-summary__error">{error}</p> : null}

      {result ? (
        <div className="servio-order-reorder__result">
          <p className="servio-copy">{resultLabel(result.result_type)}</p>
          <div className="servio-account-order-card__items">
            <div className="servio-account-order-card__item">
              <span>Запрошено позиций</span>
              <strong>{result.summary.requested_lines}</strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Добавлено</span>
              <strong>{result.summary.added_lines}</strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Скорректировано</span>
              <strong>{result.summary.adjusted_lines}</strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Недоступно</span>
              <strong>{result.summary.unavailable_lines}</strong>
            </div>
          </div>
          <div className="servio-actions">
            <a href={cartUrl || result.cart_url} className="servio-button servio-button--secondary">
              Открыть корзину
            </a>
          </div>
        </div>
      ) : null}
    </section>
  );
}
