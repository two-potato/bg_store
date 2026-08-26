import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import {
  BridgeApiError,
  formatDateTime,
  getStorefrontAccountNotifications,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Уведомления",
  description:
    "Notifications feed buyer account в Next storefront на bridge-контракте `/api/storefront/account/notifications/`.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session notifications недоступны.",
  "Нужен контракт `/api/storefront/account/notifications/`.",
  "Mark-as-read и granular notification settings остаются в следующих фазах.",
];

export default async function AccountNotificationsPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Notifications ждут session bridge"
        copy="Не удалось получить session bootstrap для ленты уведомлений."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/account/notifications/")}
        ctaLabel="Открыть legacy уведомления"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для уведомлений нужна авторизация"
        copy="Пользователь не авторизован в текущей browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/notifications")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let notifications;
  try {
    notifications = await getStorefrontAccountNotifications();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/notifications")
        : legacyStorefrontUrl("/account/notifications/");

    return (
      <AccountBlocker
        title="Не удалось загрузить уведомления"
        copy="Bridge endpoint `/api/storefront/account/notifications/` временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy уведомления"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Notifications</span>
        <h1 className="servio-page-title">Уведомления</h1>
        <p className="servio-copy servio-copy--lead">
          Единая buyer-лента событий по заказам, оплатам и связанным процессам.
        </p>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Event feed</h2>
        </div>
        {notifications.notifications.length ? (
          <div className="servio-account-order-list">
            {notifications.notifications.map((event, index) => (
              <article key={`${event.at}-${event.title}-${index}`} className="servio-account-order-row">
                <div className="servio-account-order-row__main">
                  <strong>{event.title}</strong>
                  <span>{event.subtitle || "—"}</span>
                  <span>{formatDateTime(event.at)}</span>
                </div>
                <div className="servio-account-order-row__meta">
                  {event.href ? (
                    <a href={event.href} className="servio-button servio-button--secondary">
                      Открыть
                    </a>
                  ) : (
                    <span className="servio-chip">Без перехода</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="servio-copy">Событий пока нет.</p>
        )}
      </section>
    </div>
  );
}
