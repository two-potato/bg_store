import Link from "next/link";
import type { Metadata } from "next";

import { AccountAddressesManager } from "@/components/account/account-addresses-manager";
import { AccountBlocker } from "@/components/account/account-blocker";
import {
  BridgeApiError,
  getStorefrontAccountAddresses,
  getStorefrontAccountLegalEntities,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Адреса",
  description:
    "Адресная книга buyer account в Next storefront: список адресов, добавление, default и удаление на bridge API.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session адреса недоступны.",
  "Нужен контракт `/api/storefront/account/addresses/` и mutation endpoints default/delete.",
  "Фронтенд не реализует address-валидации вне backend форм.",
];

export default async function AccountAddressesPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Адреса ждут session bridge"
        copy="Не удалось получить session bootstrap для раздела адресов."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/account/addresses/")}
        ctaLabel="Открыть legacy адреса"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для адресов нужна авторизация"
        copy="Пользователь не авторизован в текущей browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/addresses")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let addressesResponse;
  let legalResponse;

  try {
    [addressesResponse, legalResponse] = await Promise.all([
      getStorefrontAccountAddresses(),
      getStorefrontAccountLegalEntities(),
    ]);
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/addresses")
        : legacyStorefrontUrl("/account/addresses/");

    return (
      <AccountBlocker
        title="Не удалось загрузить адреса"
        copy="Bridge endpoints для account addresses/legal entities временно недоступны."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy адреса"
      />
    );
  }

  const legalEntities = legalResponse.memberships
    .map((membership) => ({
      id: membership.legal_entity.id,
      name: membership.legal_entity.name,
    }))
    .filter(
      (entity, index, source) =>
        source.findIndex((item) => item.id === entity.id) === index,
    );

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Addresses</span>
        <h1 className="servio-page-title">Адресная книга</h1>
        <p className="servio-copy servio-copy--lead">
          Управляйте адресами доставки для checkout и B2B закупок. Все операции выполняются через backend контракты.
        </p>
      </section>

      <section className="servio-account-metrics">
        <article className="servio-card servio-account-metric">
          <span>Адресов</span>
          <strong>{addressesResponse.addresses.length}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Юрлиц</span>
          <strong>{legalEntities.length}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Default адресов</span>
          <strong>{addressesResponse.addresses.filter((address) => address.is_default).length}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Связанный раздел</span>
          <strong>
            <Link href="/account/legal" className="servio-inline-link">
              Компании
            </Link>
          </strong>
        </article>
      </section>

      <AccountAddressesManager
        initialAddresses={addressesResponse.addresses}
        legalEntities={legalEntities}
        csrfToken={session.session.csrf_token}
      />
    </div>
  );
}
