import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { SavedListsManager } from "@/components/account/saved-lists-manager";
import {
  BridgeApiError,
  getStorefrontSavedLists,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Списки закупки",
  description:
    "Buyer procurement lists в Next storefront на контрактах `/api/storefront/tools/lists/*`.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session списки закупки недоступны.",
  "Нужны контракты `/api/storefront/tools/lists/*` для CRUD и move-to-cart.",
  "Фронтенд не должен хранить закупочные списки вне backend источника.",
];

export default async function ListsPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Списки закупки ждут session bridge"
        copy="Не удалось получить session bootstrap."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/lists/")}
        ctaLabel="Открыть legacy списки"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для списков нужна авторизация"
        copy="Пользователь не авторизован в browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/lists")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let lists;
  try {
    lists = await getStorefrontSavedLists();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/lists")
        : legacyStorefrontUrl("/lists/");

    return (
      <AccountBlocker
        title="Не удалось загрузить списки закупки"
        copy="Bridge endpoint `/api/storefront/tools/lists/` временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy списки"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Procurement lists</span>
        <h1 className="servio-page-title">Списки закупки</h1>
        <p className="servio-copy servio-copy--lead">
          Создавайте и обслуживайте регулярные закупочные наборы с быстрым переносом в корзину.
        </p>
      </section>
      <SavedListsManager initialLists={lists.saved_lists} csrfToken={session.session.csrf_token} />
    </div>
  );
}
