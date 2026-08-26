import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { SavedSearchesManager } from "@/components/account/saved-searches-manager";
import {
  BridgeApiError,
  getStorefrontSavedSearches,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Сохранённые поиски",
  description:
    "Saved searches buyer tools в Next storefront на контрактах `/api/storefront/tools/saved-searches/*`.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session saved searches недоступны.",
  "Нужны контракты `/api/storefront/tools/saved-searches/*` для list/create/delete.",
  "Фронтенд не хранит saved-searches локально вне backend source of truth.",
];

export default async function SavedSearchesPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Saved searches ждут session bridge"
        copy="Не удалось получить session bootstrap."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/saved-searches/")}
        ctaLabel="Открыть legacy saved searches"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для saved searches нужна авторизация"
        copy="Пользователь не авторизован в browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/saved-searches")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let searches;
  try {
    searches = await getStorefrontSavedSearches();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/saved-searches")
        : legacyStorefrontUrl("/saved-searches/");

    return (
      <AccountBlocker
        title="Не удалось загрузить saved searches"
        copy="Bridge endpoint `/api/storefront/tools/saved-searches/` временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy saved searches"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Saved searches</span>
        <h1 className="servio-page-title">Сохранённые поиски</h1>
        <p className="servio-copy servio-copy--lead">
          Сохраняйте рабочие фильтры закупки и возвращайтесь к ним одним кликом.
        </p>
      </section>
      <SavedSearchesManager initialSearches={searches.saved_searches} csrfToken={session.session.csrf_token} />
    </div>
  );
}
