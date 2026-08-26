import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { TrackBuyerWaveView } from "@/components/analytics/track-buyer-wave-view";
import { CartWorkspace } from "@/components/cart/cart-workspace";
import {
  BridgeApiError,
  getStorefrontCartSnapshot,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Корзина",
  description:
    "Cart migration boundary: Next storefront не имитирует cart бизнес-логику без backend bridge и контрактного API.",
  robots: {
    index: false,
    follow: false,
  },
};

const cartBlockers = [
  "Bridge endpoint `/api/storefront/session/bootstrap/` недоступен.",
  "Нельзя безопасно выполнять cart mutations без валидного session+csrf bootstrap.",
  "Контур остановлен до восстановления bridge, без фейковой клиентской логики корзины.",
];

export default async function CartPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Cart bridge сейчас недоступен"
        copy="Не удалось получить storefront session bootstrap. До восстановления bridge cart flow держим на безопасной границе."
        blockers={cartBlockers}
        ctaHref={legacyStorefrontUrl("/cart/")}
        ctaLabel="Открыть legacy cart"
      />
    );
  }

  if (!session.ok) {
    return (
      <AccountBlocker
        title="Cart bootstrap не инициализирован"
        copy="Storefront session bootstrap вернул неуспешный ответ."
        blockers={cartBlockers}
        ctaHref={legacyStorefrontUrl("/cart/")}
        ctaLabel="Открыть legacy cart"
      />
    );
  }

  let cartResponse;
  try {
    cartResponse = await getStorefrontCartSnapshot();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/cart")
        : loginUrlWithNext(legacyStorefrontUrl("/account/login/"), "/cart");
    return (
      <AccountBlocker
        title="Cart snapshot пока недоступен"
        copy="Не удалось получить `GET /api/storefront/cart/`. Мутации корзины отключены до восстановления контракта."
        blockers={[
          "Bridge cart read endpoint вернул ошибку.",
          "Без актуального snapshot нельзя безопасно выполнять `update/remove/clear`.",
          "Checkout и totals остаются backend-driven и не дублируются во frontend.",
        ]}
        ctaHref={loginUrl}
        ctaLabel="Проверить авторизацию"
      />
    );
  }

  return (
    <>
      <TrackBuyerWaveView
        event="cart_viewed"
        surface="cart"
        payload={{
          seller_count: cartResponse.cart.seller_count,
          total_value: cartResponse.cart.total,
        }}
      />
      <CartWorkspace
        initialCart={cartResponse.cart}
        csrfToken={session.session.csrf_token}
        authenticated={session.session.authenticated}
        loginUrl={loginUrlWithNext(session.urls.login, "/cart")}
        checkoutUrl="/checkout/"
      />
    </>
  );
}
