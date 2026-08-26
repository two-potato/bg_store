import Link from "next/link";
import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { AccountPreferencesForm } from "@/components/account/account-preferences-form";
import {
  BridgeApiError,
  getStorefrontAccountPreferences,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Предпочтения",
  description:
    "Управление buyer preferences в Next storefront: email/telegram уведомления на storefront bridge API.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session preferences недоступны.",
  "Нужен контракт `/api/storefront/account/preferences/` для GET/POST.",
  "Фронтенд не хранит notification business-логику локально.",
];

export default async function AccountPreferencesPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Preferences ждут session bridge"
        copy="Не удалось получить session bootstrap для раздела preferences."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/account/preferences/")}
        ctaLabel="Открыть legacy preferences"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для preferences нужна авторизация"
        copy="Пользователь не авторизован в текущей browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/preferences")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let preferencesResponse;
  try {
    preferencesResponse = await getStorefrontAccountPreferences();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/preferences")
        : legacyStorefrontUrl("/account/preferences/");

    return (
      <AccountBlocker
        title="Не удалось загрузить preferences"
        copy="Bridge endpoint `/api/storefront/account/preferences/` временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy preferences"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Preferences</span>
        <h1 className="servio-page-title">Предпочтения уведомлений</h1>
        <p className="servio-copy servio-copy--lead">
          Выберите каналы коммуникации для заказов и маркетинговых сообщений. Сохранение происходит через backend.
        </p>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Коммуникационные каналы</h2>
          <Link href="/account/settings" className="servio-inline-link">
            Настройки профиля
          </Link>
        </div>
        <AccountPreferencesForm
          initialPreferences={preferencesResponse.preferences}
          csrfToken={session.session.csrf_token}
        />
      </section>
    </div>
  );
}
