import Link from "next/link";
import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { AccountSettingsForm } from "@/components/account/account-settings-form";
import {
  BridgeApiError,
  getStorefrontAccountSettings,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Настройки аккаунта",
  description:
    "Настройки buyer профиля в Next storefront: контактные данные и коммуникационные реквизиты на storefront bridge API.",
  robots: {
    index: false,
    follow: false,
  },
};

const settingsBlockers = [
  "Без авторизованной browser session настройки недоступны.",
  "Storefront bridge endpoint `/api/storefront/account/settings/` должен быть доступен для GET/POST.",
  "Фронтенд не дублирует profile-валидации backend.",
];

export default async function AccountSettingsPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Настройки ждут session bridge"
        copy="Не удалось получить session bootstrap для account settings."
        blockers={settingsBlockers}
        ctaHref={legacyStorefrontUrl("/account/")}
        ctaLabel="Открыть legacy account"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для настроек нужна авторизация"
        copy="Пользователь не авторизован в текущей browser session."
        blockers={settingsBlockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/settings")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let settingsResponse;
  try {
    settingsResponse = await getStorefrontAccountSettings();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/settings")
        : legacyStorefrontUrl("/account/settings/");

    return (
      <AccountBlocker
        title="Не удалось загрузить настройки"
        copy="Bridge endpoint `/api/storefront/account/settings/` временно недоступен."
        blockers={settingsBlockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy настройки"
      />
    );
  }

  const settings = settingsResponse.settings;

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Account settings</span>
        <h1 className="servio-page-title">Настройки профиля</h1>
        <p className="servio-copy servio-copy--lead">
          Обновляйте контактные данные buyer-профиля. Валидация и сохранение выполняются только на backend.
        </p>
      </section>

      <section className="servio-account-metrics">
        <article className="servio-card servio-account-metric">
          <span>Username</span>
          <strong>{settings.username || "—"}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Role</span>
          <strong>{settings.role || "buyer"}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Email login</span>
          <strong>{settings.email || "—"}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Telegram</span>
          <strong>{settings.telegram.linked ? `@${settings.telegram.username || "linked"}` : "Не подключён"}</strong>
        </article>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Контакты для заказов</h2>
          <Link href="/account/preferences" className="servio-inline-link">
            Предпочтения уведомлений
          </Link>
        </div>
        <AccountSettingsForm initialSettings={settings} csrfToken={session.session.csrf_token} />
      </section>
    </div>
  );
}
