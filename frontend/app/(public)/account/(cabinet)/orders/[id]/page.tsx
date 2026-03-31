import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { OrderReorderAction } from "@/components/account/order-reorder-action";
import { AccountBlocker } from "@/components/account/account-blocker";
import { BuyerWaveEventLink } from "@/components/analytics/buyer-wave-event-link";
import { TrackBuyerWaveView } from "@/components/analytics/track-buyer-wave-view";
import {
  BridgeApiError,
  formatDateTime,
  getStorefrontOrderDetail,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { formatPrice } from "@/lib/catalog-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

type OrderDetailProps = {
  params: Promise<{ id: string }>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: OrderDetailProps): Promise<Metadata> {
  const { id } = await params;
  return {
    title: `Заказ #${id}`,
    description:
      "Buyer order detail в Next storefront: timeline, items, payment/tracking context и reorder flow через storefront bridge.",
    robots: {
      index: false,
      follow: false,
    },
  };
}

const remainingBlockers = [
  "Нет отдельного bridge endpoint для cancel action из Next detail.",
  "Нет bridge mutation endpoints для claims/support create/update в Next detail.",
  "Tracking остаётся отдельным legacy-экраном до выделенного Next tracking surface.",
];

function timelineClass(state: "done" | "pending" | "issue") {
  if (state === "done") {
    return "servio-order-timeline__item is-done";
  }
  if (state === "issue") {
    return "servio-order-timeline__item is-issue";
  }
  return "servio-order-timeline__item";
}

export default async function OrderDetailPage({ params }: OrderDetailProps) {
  const { id } = await params;
  const orderId = Number(id);

  if (!Number.isInteger(orderId) || orderId <= 0) {
    notFound();
  }

  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title={`Order detail #${orderId} ждёт bridge`}
        copy="Session bootstrap недоступен, поэтому detail flow безопасно остановлен."
        blockers={remainingBlockers}
        ctaHref={legacyStorefrontUrl(`/account/orders/${orderId}/`)}
        ctaLabel="Открыть legacy detail"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title={`Для заказа #${orderId} нужна авторизация`}
        copy="Пользователь не авторизован в текущей browser session."
        blockers={remainingBlockers}
        ctaHref={loginUrlWithNext(session.urls.login, `/account/orders/${orderId}`)}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let detail;
  try {
    detail = await getStorefrontOrderDetail(orderId);
  } catch (error) {
    if (error instanceof BridgeApiError && error.status === 404) {
      notFound();
    }
    if (error instanceof BridgeApiError && error.status === 401) {
      return (
        <AccountBlocker
          title={`Order detail #${orderId} требует повторного входа`}
          copy="Order detail endpoint вернул 401."
          blockers={remainingBlockers}
          ctaHref={loginUrlWithNext(session.urls.login, `/account/orders/${orderId}`)}
          ctaLabel="Повторить вход"
        />
      );
    }

    return (
      <AccountBlocker
        title={`Не удалось загрузить заказ #${orderId}`}
        copy="Storefront bridge endpoint `/api/storefront/orders/{id}/` временно недоступен."
        blockers={remainingBlockers}
        ctaHref={legacyStorefrontUrl(`/account/orders/${orderId}/`)}
        ctaLabel="Открыть legacy detail"
      />
    );
  }

  const order = detail.order;

  return (
    <div className="servio-account-main">
      <TrackBuyerWaveView
        event="order_detail_viewed"
        surface="order_detail"
        payload={{
          order_id: order.id,
          total_value: order.total,
          approval_state: order.approval_status,
          customer_type: order.customer_type,
        }}
      />

      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Order detail</span>
        <h1 className="servio-page-title">Заказ #{order.id}</h1>
        <p className="servio-copy servio-copy--lead">
          Реальный detail-flow поверх bridge-контракта: состав заказа, timeline, payment/tracking context и reorder
          без переноса backend бизнес-логики.
        </p>
        <div className="servio-actions">
          <Link href="/account/orders" className="servio-button servio-button--secondary">
            Назад к заказам
          </Link>
          <a href={legacyStorefrontUrl(order.actions.legacy_detail_url)} className="servio-button servio-button--ghost">
            Legacy detail
          </a>
        </div>
      </section>

      <section className="servio-account-metrics">
        <article className="servio-card servio-account-metric">
          <span>Статус</span>
          <strong>{order.status_display}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Согласование</span>
          <strong>{order.approval_status_display}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Итого</span>
          <strong>{formatPrice(order.total)}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Создан</span>
          <strong>{formatDateTime(order.created_at)}</strong>
        </article>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Procurement timeline</h2>
        </div>
        <div className="servio-order-timeline">
          {order.timeline.map((step) => (
            <article key={step.key} className={timelineClass(step.state)}>
              <strong>{step.title}</strong>
              <span>{step.label}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Состав заказа</h2>
        </div>
        {order.items.length ? (
          <div className="servio-order-items">
            {order.items.map((item) => (
              <article key={item.id} className="servio-order-item">
                <div className="servio-order-item__main">
                  <img
                    src={item.product.image_url || "/static/shopfront/product-placeholder.svg"}
                    alt={item.product.name}
                    className="servio-cart-item__image"
                  />
                  <div>
                    <strong>{item.name}</strong>
                    <span>SKU {item.product.sku}</span>
                  </div>
                </div>
                <div>
                  <span>{item.active_qty} шт.</span>
                  <strong>{formatPrice(item.row_total)}</strong>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="servio-copy">Позиции заказа недоступны.</p>
        )}
      </section>

      <section className="servio-account-two-col">
        <article className="servio-card">
          <div className="servio-account-section-head">
            <h2 className="servio-card-title">Delivery / payment context</h2>
          </div>
          <div className="servio-account-order-card__items">
            <div className="servio-account-order-card__item">
              <span>Delivery method</span>
              <strong>{order.delivery_method_display}</strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Payment method</span>
              <strong>{order.payment_method_display}</strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Юрлицо</span>
              <strong>{order.legal_entity.name || "—"}</strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Адрес</span>
              <strong>
                {order.delivery_address.city || order.delivery_address.street
                  ? `${order.delivery_address.city}, ${order.delivery_address.street}`
                  : "—"}
              </strong>
            </div>
          </div>

          <div className="servio-actions">
            <BuyerWaveEventLink
              href={legacyStorefrontUrl(order.payment.invoice_url)}
              className="servio-button servio-button--secondary"
              event="invoice_download_clicked"
              surface="order_detail"
              payload={{
                order_id: order.id,
              }}
            >
              Скачать invoice
            </BuyerWaveEventLink>
            <BuyerWaveEventLink
              href={order.tracking.tracking_url}
              className="servio-button servio-button--secondary"
              event="order_tracking_viewed"
              surface="order_detail"
              payload={{
                order_id: order.id,
              }}
            >
              Tracking page
            </BuyerWaveEventLink>
            {order.payment.can_retry ? (
              <a href={legacyStorefrontUrl(order.payment.retry_url)} className="servio-button servio-button--secondary">
                Повторить оплату
              </a>
            ) : null}
          </div>
        </article>

        <aside className="servio-card servio-card--soft">
          <div className="servio-account-section-head">
            <h2 className="servio-card-title">Reorder</h2>
          </div>
          {order.actions.can_reorder ? (
            <OrderReorderAction
              orderId={order.id}
              csrfToken={session.session.csrf_token}
              reorderUrl={order.actions.reorder_url}
              cartUrl="/cart"
            />
          ) : (
            <p className="servio-copy">Повтор заказа недоступен для текущего пользователя.</p>
          )}
        </aside>
      </section>

      <section className="servio-account-two-col">
        <article className="servio-card">
          <div className="servio-account-section-head">
            <h2 className="servio-card-title">Claims / support summary</h2>
          </div>
          <div className="servio-account-order-card__items">
            <div className="servio-account-order-card__item">
              <span>Claims</span>
              <strong>
                {order.support.open_claims_count} / {order.support.claims_count}
              </strong>
            </div>
            <div className="servio-account-order-card__item">
              <span>Support tickets</span>
              <strong>
                {order.support.open_support_tickets_count} / {order.support.support_tickets_count}
              </strong>
            </div>
          </div>
          <p className="servio-copy">
            Создание claims/support пока остаётся в legacy detail до появления phase-2 mutation контрактов.
          </p>
        </article>

        <aside className="servio-card servio-account-state servio-account-state--warning">
          <span className="servio-eyebrow">Остаточные blockers</span>
          <ul className="servio-account-state__list">
            {remainingBlockers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </aside>
      </section>
    </div>
  );
}
