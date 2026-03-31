import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { TrackBuyerWaveView } from "@/components/analytics/track-buyer-wave-view";
import { FavoritesManager } from "@/components/account/favorites-manager";
import {
  BridgeApiError,
  getStorefrontFavorites,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Избранное",
  description:
    "Buyer favorites в Next storefront на bridge endpoint `/api/storefront/tools/favorites/`.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session избранное недоступно.",
  "Нужны контракты `/api/storefront/tools/favorites/` и `/toggle/`.",
  "Избранное не должно жить в локальном state без backend source of truth.",
];

export default async function FavoritesPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Избранное ждёт session bridge"
        copy="Не удалось получить session bootstrap."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/favorites/")}
        ctaLabel="Открыть legacy избранное"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для избранного нужна авторизация"
        copy="Пользователь не авторизован в browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/favorites")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let favorites;
  try {
    favorites = await getStorefrontFavorites();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/favorites")
        : legacyStorefrontUrl("/favorites/");

    return (
      <AccountBlocker
        title="Не удалось загрузить избранное"
        copy="Bridge endpoint для favorites временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy избранное"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <TrackBuyerWaveView
        event="favorites_viewed"
        surface="favorites"
        payload={{
          favorites_count: favorites.favorites.length,
        }}
      />
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Favorites</span>
        <h1 className="servio-page-title">Избранное</h1>
        <p className="servio-copy servio-copy--lead">
          Быстрый доступ к часто покупаемым товарам и shortlist для повторных закупок.
        </p>
      </section>
      <FavoritesManager initialFavorites={favorites.favorites} csrfToken={session.session.csrf_token} />
    </div>
  );
}
