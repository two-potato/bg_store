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
  title: "Buyer Account",
  description:
    "Buyer workspace в Next storefront: фокус на день, procurement queue и быстрый доступ к account sections.",
  robots: {
    index: false,
    follow: false,
  },
};

const baseBlockers = [
  "Нужен рабочий session bootstrap `/api/storefront/session/bootstrap/`.",
  "Нужен account bootstrap `/api/storefront/account/bootstrap/` для метрик и очередей.",
  "Без этих контрактов account shell не должен симулировать buyer-данные на клиенте.",
];

export default async function AccountHomePage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Account shell ждёт session bridge"
        copy="Не удалось получить storefront session bootstrap. Контур account безопасно остановлен без имитации данных."
        blockers={baseBlockers}
        ctaHref={legacyStorefrontUrl("/account/")}
        ctaLabel="Открыть legacy account"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для buyer account нужна авторизация"
        copy="Session bridge доступен, но пользователь не авторизован. Для входа используем legacy auth flow."
        blockers={[
          "Account bootstrap возвращает данные только для authenticated session.",
          "Без user session нельзя показывать персональные метрики и queues.",
          "Переход к orders/detail остаётся защищённым backend-контрактом.",
        ]}
        ctaHref={loginUrlWithNext(session.urls.login, "/account")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let account;
  try {
    account = await getStorefrontAccountBootstrap();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account")
        : loginUrlWithNext(legacyStorefrontUrl("/account/login/"), "/account");

    return (
      <AccountBlocker
        title="Account bootstrap временно недоступен"
        copy="Не удалось загрузить данные buyer workspace из `/api/storefront/account/bootstrap/`."
        blockers={[
          "Account shell не может безопасно вывести queues и metrics.",
          "Фронтенд не должен дублировать backend-логику расчётов метрик.",
          "До восстановления контракта переход выполняется в legacy.",
        ]}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy account"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <TrackBuyerWaveView
        event="account_dashboard_viewed"
        surface="account_dashboard"
        payload={{
          orders_count: account.metrics.orders_count,
          favorites_count: account.metrics.favorites_count,
          saved_searches_count: account.metrics.saved_searches_count,
        }}
      />

      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Рабочий центр</span>
        <h1 className="servio-page-title">Личный кабинет</h1>
        <p className="servio-copy servio-copy--lead">
          Buyer workspace в Next storefront: фокус на ежедневном workload, заказах и account-инструментах без переноса
          бизнес-логики backend во frontend.
        </p>
        <div className="servio-actions">
          <Link href="/account/orders" className="servio-button servio-button--primary">
            Открыть заказы
          </Link>
          <Link href="/catalog" className="servio-button servio-button--secondary">
            Перейти в каталог
          </Link>
        </div>
      </section>

      <section className="servio-account-metrics" aria-label="Focus today">
        <article className="servio-card servio-account-metric">
          <span>Заказы</span>
          <strong>{account.metrics.orders_count}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Избранное</span>
          <strong>{account.metrics.favorites_count}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Saved searches</span>
          <strong>{account.metrics.saved_searches_count}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Компании / адреса</span>
          <strong>
            {account.metrics.entities_count} / {account.metrics.addresses_count}
          </strong>
        </article>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Procurement queue</h2>
          <Link href="/account/orders" className="servio-inline-link">
            Вся лента заказов
          </Link>
        </div>
        <div className="servio-account-order-list">
          {(account.queues.unpaid_orders.length
            ? account.queues.unpaid_orders
            : account.queues.recent_orders
          ).map((order) => (
            <article key={order.id} className="servio-account-order-row">
              <div className="servio-account-order-row__main">
                <strong>Заказ #{order.id}</strong>
                <span>{formatDateTime(order.created_at)}</span>
              </div>
              <div className="servio-account-order-row__meta">
                <span className="servio-chip">{order.status_display}</span>
                <span className="servio-chip">{order.approval_status_display}</span>
                <span className="servio-chip">{formatPrice(order.total)}</span>
                <Link href={`/account/orders/${order.id}`} className="servio-button servio-button--ghost">
                  Открыть
                </Link>
              </div>
            </article>
          ))}
          {!account.queues.unpaid_orders.length &&
          !account.queues.recent_orders.length ? (
            <div className="servio-empty-state servio-card servio-card--soft">
              <h3 className="servio-card-title">У вас пока нет заказов</h3>
              <p className="servio-copy">После первой закупки здесь появится операционная очередь и быстрые действия.</p>
              <div className="servio-actions">
                <Link href="/catalog" className="servio-button servio-button--primary">
                  Перейти в каталог
                </Link>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className="servio-card servio-card--soft">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Аккаунт и операционные разделы</h2>
        </div>
        <p className="servio-copy">
          Ключевые buyer-секции доступны в Next storefront и работают поверх bridge API: настройки профиля,
          preferences, адреса, компании и уведомления.
        </p>
        <div className="servio-actions">
          <Link href="/account/settings" className="servio-button servio-button--secondary">
            Настройки
          </Link>
          <Link href="/account/addresses" className="servio-button servio-button--secondary">
            Адреса
          </Link>
          <Link href="/account/legal" className="servio-button servio-button--secondary">
            Компании
          </Link>
          <Link href="/account/notifications" className="servio-button servio-button--secondary">
            Уведомления
          </Link>
          <Link href="/account/preferences" className="servio-button servio-button--secondary">
            Предпочтения
          </Link>
          <Link href="/account/favorites" className="servio-button servio-button--secondary">
            Избранное
          </Link>
          <Link href="/account/lists" className="servio-button servio-button--secondary">
            Списки закупки
          </Link>
          <Link href="/account/saved-searches" className="servio-button servio-button--secondary">
            Saved searches
          </Link>
        </div>
      </section>
    </div>
  );
}
