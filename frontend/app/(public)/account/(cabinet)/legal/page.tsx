import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import {
  BridgeApiError,
  formatDateTime,
  getStorefrontAccountLegalEntities,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Компании",
  description:
    "B2B legal workspace в Next storefront: memberships, company workspaces и creation requests.",
  robots: {
    index: false,
    follow: false,
  },
};

const blockers = [
  "Без авторизованной browser session legal workspace недоступен.",
  "Нужен контракт `/api/storefront/account/legal-entities/`.",
  "Создание/редактирование юрлица остаётся в следующем phase контрактов.",
];

export default async function AccountLegalPage() {
  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title="Раздел компаний ждёт session bridge"
        copy="Не удалось получить session bootstrap для legal workspace."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl("/account/legal/")}
        ctaLabel="Открыть legacy компании"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для компаний нужна авторизация"
        copy="Пользователь не авторизован в текущей browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, "/account/legal")}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let legal;
  try {
    legal = await getStorefrontAccountLegalEntities();
  } catch (error) {
    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, "/account/legal")
        : legacyStorefrontUrl("/account/legal/");

    return (
      <AccountBlocker
        title="Не удалось загрузить компании"
        copy="Bridge endpoint `/api/storefront/account/legal-entities/` временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy компании"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">Legal entities</span>
        <h1 className="servio-page-title">Компании и B2B workspace</h1>
        <p className="servio-copy servio-copy--lead">
          Раздел показывает memberships, рабочие пространства и заявки на создание юрлица. Мутации остаются в
          следующей фазе контрактов.
        </p>
      </section>

      <section className="servio-account-metrics">
        <article className="servio-card servio-account-metric">
          <span>Memberships</span>
          <strong>{legal.memberships.length}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Workspace</span>
          <strong>{legal.company_workspaces.length}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Заявок</span>
          <strong>{legal.creation_requests.length}</strong>
        </article>
        <article className="servio-card servio-account-metric">
          <span>Default next step</span>
          <strong>Phase 2B</strong>
        </article>
      </section>

      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Memberships</h2>
        </div>
        {legal.memberships.length ? (
          <div className="servio-account-order-list">
            {legal.memberships.map((membership) => (
              <article key={membership.id} className="servio-account-order-row">
                <div className="servio-account-order-row__main">
                  <strong>{membership.legal_entity.name}</strong>
                  <span>ИНН: {membership.legal_entity.inn || "—"}</span>
                  <span>Роль: {membership.role.name || membership.role.code || "—"}</span>
                </div>
                <div className="servio-account-order-row__meta">
                  <span className="servio-chip">БИК: {membership.legal_entity.bik || "—"}</span>
                  <span className="servio-chip">Счёт: {membership.legal_entity.checking_account || "—"}</span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="servio-copy">У вас пока нет привязанных юрлиц. Они нужны для B2B закупок и адресов доставки.</p>
        )}
      </section>

      <section className="servio-account-two-col">
        <article className="servio-card">
          <div className="servio-account-section-head">
            <h2 className="servio-card-title">Company workspaces</h2>
          </div>
          {legal.company_workspaces.length ? (
            <div className="servio-account-order-list">
              {legal.company_workspaces.map((workspace) => (
                <article key={workspace.company_id} className="servio-account-order-row">
                  <div className="servio-account-order-row__main">
                    <strong>{workspace.display_name}</strong>
                    <span>Роль: {workspace.membership_role || "—"}</span>
                  </div>
                  <div className="servio-account-order-row__meta">
                    <span className="servio-chip">
                      Approval: {workspace.approval_policy.enabled ? "включено" : "выключено"}
                    </span>
                    <span className="servio-chip">
                      Approvers: {workspace.approval_policy.required_approvals_count}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="servio-copy">Пока нет company workspace для текущего пользователя.</p>
          )}
        </article>

        <article className="servio-card servio-card--soft">
          <div className="servio-account-section-head">
            <h2 className="servio-card-title">Заявки на юрлицо</h2>
          </div>
          {legal.creation_requests.length ? (
            <div className="servio-account-order-list">
              {legal.creation_requests.map((request) => (
                <article key={request.id} className="servio-account-order-row">
                  <div className="servio-account-order-row__main">
                    <strong>{request.name}</strong>
                    <span>ИНН: {request.inn || "—"}</span>
                    <span>{formatDateTime(request.created_at)}</span>
                  </div>
                  <div className="servio-account-order-row__meta">
                    <span className="servio-chip">{request.status.name || request.status.code || "—"}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="servio-copy">
              Заявок пока нет. Создание новых заявок остаётся в legacy до следующих mutation контрактов.
            </p>
          )}
        </article>
      </section>
    </div>
  );
}
