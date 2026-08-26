import Link from "next/link";
import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { TrackBuyerWaveView } from "@/components/analytics/track-buyer-wave-view";
import {
  BridgeApiError,
  formatDateTime,
  getStorefrontAccountBootstrap,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { formatPrice } from "@/lib/catalog-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Мои заказы",
  description:
    "Buyer orders surface в Next storefront: безопасная лента заказов на доступных bridge-контрактах и явные blockers для недостающих endpoints.",
  robots: {
    index: false,
    follow: false,
  },
};

const ordersContractBlockers = [
  "Нет bridge endpoint для полной пагинируемой ленты buyer orders (только queues в account bootstrap).",
  "Нет контрактов фильтрации/сортировки и server pagination для больших buyer histories.",
  "Часть order actions (cancel/support/claims) остаётся в legacy до phase-2 mutation endpoints.",
];

export default async function OrdersPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Orders surface ждёт session bridge"
        copy="Session bootstrap недоступен, поэтому orders surface не может безопасно открыть buyer queue."
        blockers={ordersContractBlockers}
        ctaHref={legacyStorefrontUrl("/account/orders/")}
        ctaLabel="Открыть legacy orders"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для заказов требуется авторизация"
        copy="Пользователь не авторизован в browser session. Переводим в legacy login flow."
        blockers={ordersContractBlockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/orders")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let account;
  try {
    account = await getStorefrontAccountBootstrap();
  } catch (error) {
    if (error instanceof BridgeApiError && error.status === 401) {
      return (
        <AccountBlocker
          title="Orders bootstrap вернул 401"
          copy="Сессия больше невалидна для account bootstrap."
          blockers={ordersContractBlockers}
          ctaHref={loginUrlWithNext(session.urls.login, "/account/orders")}
          ctaLabel="Повторить вход"
        />
      );
    }
    return (
      <AccountBlocker
        title="Orders bootstrap временно недоступен"
        copy="Не удалось получить buyer queues из `/api/storefront/account/bootstrap/`."
        blockers={ordersContractBlockers}
        ctaHref={legacyStorefrontUrl("/account/orders/")}
        ctaLabel="Открыть legacy orders"
      />
    );
  }

  const orders = [...account.queues.unpaid_orders, ...account.queues.recent_orders]
    .filter((order, index, source) => source.findIndex((item) => item.id === order.id) === index)
    .sort((a, b) => b.id - a.id);

  return (
    <div className="servio-account-main">
      <TrackBuyerWaveView
        event="orders_list_viewed"
        surface="orders_list"
        payload={{
          orders_count: orders.length,
        }}
      />

      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Orders</span>
        <h1 className="servio-page-title">Мои заказы</h1>
        <p className="servio-copy servio-copy--lead">
          Partial delivery: показываем доступную buyer-ленту из account bootstrap. Detail/reorder уже перенесены на
          bridge, но full list pagination и часть mutation actions остаются следующей фазой.
        </p>
        <div className="servio-actions">
          <Link href="/catalog" className="servio-button servio-button--secondary">
            Перейти в каталог
          </Link>
          <Link href="/account/lists" className="servio-button servio-button--ghost">
            Черновики закупки
          </Link>
        </div>
      </section>

      {orders.length ? (
        <section className="servio-account-order-grid" aria-label="Лента заказов">
          {orders.map((order) => (
            <article key={order.id} className="servio-card servio-account-order-card">
              <div className="servio-account-order-card__head">
                <div>
                  <div className="servio-account-order-card__title">Заказ #{order.id}</div>
                  <div className="servio-account-order-card__date">{formatDateTime(order.created_at)}</div>
                </div>
                <strong>{formatPrice(order.total)}</strong>
              </div>

              <div className="servio-account-order-card__statuses">
                <span className="servio-chip">{order.status_display}</span>
                <span className="servio-chip">{order.approval_status_display}</span>
                <span className="servio-chip">{order.legal_entity.name || "Без юрлица"}</span>
              </div>

              <div className="servio-account-order-card__items">
                <div className="servio-account-order-card__item">
                  <span>Subtotal</span>
                  <strong>{formatPrice(order.subtotal)}</strong>
                </div>
                <div className="servio-account-order-card__item">
                  <span>Discount</span>
                  <strong>{formatPrice(order.discount_amount)}</strong>
                </div>
              </div>

              <div className="servio-account-order-card__actions">
                <Link href={`/account/orders/${order.id}`} className="servio-button servio-button--primary">
                  Открыть заказ
                </Link>
                <a
                  href={legacyStorefrontUrl(`/account/orders/${order.id}/`)}
                  className="servio-button servio-button--secondary"
                >
                  Полный legacy flow
                </a>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="servio-card servio-empty-state servio-card--soft">
          <h2 className="servio-card-title">У вас пока нет заказов</h2>
          <p className="servio-copy">После первой закупки здесь появятся order cards и быстрый переход в детали.</p>
          <div className="servio-actions">
            <Link href="/catalog" className="servio-button servio-button--primary">
              Перейти в каталог
            </Link>
          </div>
        </section>
      )}

      <section className="servio-card servio-account-state servio-account-state--warning">
        <span className="servio-eyebrow">Contract gaps</span>
        <h2 className="servio-card-title">Что ещё нужно для полного orders parity</h2>
        <ul className="servio-account-state__list">
          {ordersContractBlockers.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
