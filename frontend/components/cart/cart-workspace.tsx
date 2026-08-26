"use client";

import Link from "next/link";
import { useState } from "react";

import type { BridgeCartSnapshot } from "@/lib/buyer-account-api";
import { trackBuyerWaveEvent, type BuyerWaveEvent } from "@/lib/buyer-wave-analytics";
import { formatPrice } from "@/lib/catalog-api";

type CartWorkspaceProps = {
  initialCart: BridgeCartSnapshot;
  csrfToken: string;
  authenticated: boolean;
  loginUrl: string;
  checkoutUrl: string;
};

type CartMutationEndpoint =
  | "/api/storefront/cart/update/"
  | "/api/storefront/cart/remove/"
  | "/api/storefront/cart/clear/";

type CartMutationResponse = {
  ok: boolean;
  error?: string;
  cart: BridgeCartSnapshot;
};


export function CartWorkspace({
  initialCart,
  csrfToken,
  authenticated,
  loginUrl,
  checkoutUrl,
}: CartWorkspaceProps) {
  const [cart, setCart] = useState(initialCart);
  const [pendingProductId, setPendingProductId] = useState<number | null>(null);
  const [isClearing, setIsClearing] = useState(false);
  const [liveMessage, setLiveMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function mutateCart(
    endpoint: CartMutationEndpoint,
    payload: Record<string, unknown>,
    successMessage: string,
    productId?: number,
    analytics?: {
      event: BuyerWaveEvent;
      payload?: Record<string, unknown>;
    },
  ) {
    if (endpoint === "/api/storefront/cart/clear/") {
      setIsClearing(true);
    } else if (productId) {
      setPendingProductId(productId);
    }
    setErrorMessage("");

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify(payload),
      });

      const result = (await response.json()) as CartMutationResponse;
      if (!response.ok || !result.ok) {
        setErrorMessage(result.error || "Не удалось обновить корзину.");
        return;
      }

      setCart(result.cart);
      setLiveMessage(successMessage);
      if (analytics) {
        void trackBuyerWaveEvent(analytics.event, "cart", analytics.payload || {});
      }
    } catch {
      setErrorMessage("Ошибка сети при обновлении корзины.");
    } finally {
      setPendingProductId(null);
      setIsClearing(false);
    }
  }

  const totalItems = cart.seller_groups.reduce(
    (sum, group) => sum + group.items.reduce((s, item) => s + item.qty, 0),
    0,
  );

  return (
    <section className="servio-cart-workspace">
      <div className="servio-cart-head">
        <div>
          <nav className="servio-breadcrumbs" aria-label="Breadcrumb">
            <Link href="/">Главная</Link>
            <span>/</span>
            <span>Корзина</span>
          </nav>
          <h1 className="servio-page-title">
            {cart.is_empty ? "Корзина" : `Корзина (${totalItems})`}
          </h1>
        </div>
        {!cart.is_empty ? (
          <button
            type="button"
            className="servio-button servio-button--secondary"
            onClick={() =>
              mutateCart(
                "/api/storefront/cart/clear/",
                {},
                "Корзина очищена.",
                undefined,
                {
                  event: "cart_cleared",
                  payload: {
                    seller_count: cart.seller_count,
                    total_value: cart.total,
                  },
                },
              )
            }
            disabled={isClearing}
          >
            {isClearing ? "Очищаем..." : "Очистить корзину"}
          </button>
        ) : null}
      </div>

      <p className="servio-cart-live" aria-live="polite">
        {liveMessage}
      </p>

      {!cart.is_empty ? (
        <div className="servio-cart-layout">
          <section className="servio-cart-groups">
            {cart.seller_groups.map((group) => (
              <article key={`${group.title}-${group.slug}`} className="servio-card servio-cart-seller-group">
                <div className="servio-cart-seller-group__head">
                  <div>
                    <span className="servio-eyebrow">Поставщик</span>
                    <h2 className="servio-card-title">{group.title}</h2>
                  </div>
                  <strong>{formatPrice(group.subtotal)}</strong>
                </div>

                <div className="servio-cart-items">
                  {group.items.map((item) => {
                    const isPending = pendingProductId === item.product.id;
                    return (
                      <article key={item.product.id} className="servio-cart-item">
                        <div className="servio-cart-item__main">
                          <img
                            src={item.product.image_url || "/static/shopfront/product-placeholder.svg"}
                            alt={item.product.name}
                            className="servio-cart-item__image"
                          />
                          <div className="servio-cart-item__copy">
                            <strong>{item.product.name}</strong>
                            <span>
                              {formatPrice(item.product.price)} · SKU {item.product.sku}
                            </span>
                            <span>MOQ: {item.product.min_order_qty}</span>
                          </div>
                        </div>

                        <div className="servio-cart-item__controls">
                          <div className="servio-cart-item__stepper" aria-label={`Управление количеством ${item.product.name}`}>
                            <button
                              type="button"
                              className="servio-button servio-button--ghost"
                              onClick={() =>
                                mutateCart(
                                  "/api/storefront/cart/update/",
                                  { product_id: item.product.id, op: "dec" },
                                  "Количество уменьшено.",
                                  item.product.id,
                                  {
                                    event: "cart_qty_decremented",
                                    payload: {
                                      product_id: item.product.id,
                                      source_surface: "cart",
                                    },
                                  },
                                )
                              }
                              disabled={isPending}
                              aria-label={`Уменьшить количество ${item.product.name}`}
                            >
                              −
                            </button>
                            <span>{item.qty}</span>
                            <button
                              type="button"
                              className="servio-button servio-button--ghost"
                              onClick={() =>
                                mutateCart(
                                  "/api/storefront/cart/update/",
                                  { product_id: item.product.id, op: "inc" },
                                  "Количество увеличено.",
                                  item.product.id,
                                  {
                                    event: "cart_qty_incremented",
                                    payload: {
                                      product_id: item.product.id,
                                      source_surface: "cart",
                                    },
                                  },
                                )
                              }
                              disabled={isPending}
                              aria-label={`Увеличить количество ${item.product.name}`}
                            >
                              +
                            </button>
                          </div>

                          <button
                            type="button"
                            className="servio-button servio-button--danger"
                            onClick={() =>
                              mutateCart(
                                "/api/storefront/cart/remove/",
                                { product_id: item.product.id },
                                "Товар удалён из корзины.",
                                item.product.id,
                                {
                                  event: "cart_item_removed",
                                  payload: {
                                    product_id: item.product.id,
                                    source_surface: "cart",
                                  },
                                },
                              )
                            }
                            disabled={isPending}
                            aria-label={`Удалить ${item.product.name} из корзины`}
                          >
                            Удалить
                          </button>
                        </div>

                        <div className="servio-cart-item__total">{formatPrice(item.row_total)}</div>
                      </article>
                    );
                  })}
                </div>
              </article>
            ))}
          </section>

          <aside className="servio-card servio-cart-summary" style={{ position: "sticky", top: "1.5rem", alignSelf: "flex-start" }}>
            <span className="servio-eyebrow">Итоги заказа</span>
            <div className="servio-cart-summary__line">
              <span>Подытог</span>
              <strong>{formatPrice(cart.subtotal)}</strong>
            </div>
            {Number(cart.profile_discount_amount) > 0 ? (
              <div className="servio-cart-summary__line">
                <span>Скидка профиля ({cart.discount_percent}%)</span>
                <strong>-{formatPrice(cart.profile_discount_amount)}</strong>
              </div>
            ) : null}
            {Number(cart.coupon_discount_amount) > 0 ? (
              <div className="servio-cart-summary__line">
                <span>Промокод {cart.coupon.code || ""}</span>
                <strong>-{formatPrice(cart.coupon_discount_amount)}</strong>
              </div>
            ) : null}
            <div className="servio-cart-summary__line is-total">
              <span>Итого</span>
              <strong>{formatPrice(cart.total)}</strong>
            </div>

            {cart.seller_count > 1 ? (
              <p className="servio-account-profile__notice">
                В корзине товары от {cart.seller_count} поставщиков. Заказы будут оформлены отдельно по каждому поставщику.
              </p>
            ) : null}

            {cart.coupon.validation_error ? (
              <p className="servio-cart-summary__error">{cart.coupon.validation_error}</p>
            ) : null}

            {errorMessage ? <p className="servio-cart-summary__error">{errorMessage}</p> : null}

            <div className="servio-actions">
              {authenticated ? (
                <a
                  href={checkoutUrl}
                  className="servio-button servio-button--primary"
                  onClick={() =>
                    void trackBuyerWaveEvent("cart_checkout_clicked", "cart", {
                      seller_count: cart.seller_count,
                      total_value: cart.total,
                    })
                  }
                >
                  Оформить заказ
                </a>
              ) : (
                <a href={loginUrl} className="servio-button servio-button--primary">
                  Войти для оформления
                </a>
              )}
              <Link href="/catalog" className="servio-button servio-button--secondary">
                Продолжить покупки
              </Link>
            </div>
          </aside>
        </div>
      ) : (
        <section className="servio-card servio-empty-state servio-card--soft">
          <h2 className="servio-card-title">Корзина пуста</h2>
          <p className="servio-copy">
            Добавьте товары из каталога — они появятся здесь с разбивкой по поставщикам и итоговой суммой.
          </p>
          <div className="servio-actions">
            <Link href="/catalog" className="servio-button servio-button--primary">
              Перейти в каталог
            </Link>
          </div>
        </section>
      )}
    </section>
  );
}
