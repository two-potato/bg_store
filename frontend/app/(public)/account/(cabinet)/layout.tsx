import type { ReactNode } from "react";

import { AccountNav } from "@/components/account/account-nav";
import { getStorefrontSessionBootstrap } from "@/lib/buyer-account-api";

export default async function AccountLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  let session: Awaited<ReturnType<typeof getStorefrontSessionBootstrap>> | null = null;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    session = null;
  }
  const user = session?.user;

  return (
    <div className="servio-account">
      <aside className="servio-account__aside">
        <section className="servio-card servio-account-profile">
          <span className="servio-eyebrow">Buyer account</span>
          <h2 className="servio-card-title">
            {user?.username || "Требуется session bridge"}
          </h2>
          <p className="servio-copy">
            {user
              ? "Кабинет покупателя в Next storefront использует backend JSON bridge и не переносит бизнес-логику backend в клиент."
              : "Для загрузки buyer account/orders нужен рабочий session bootstrap из `/api/storefront/session/bootstrap/`."}
          </p>
          {user ? (
            <div className="servio-account-profile__facts">
              <span className="servio-chip">Скидка: {user.discount}%</span>
              <span className="servio-chip">
                Роль: {user.role || "buyer"}
              </span>
              {user.telegram.linked ? (
                <span className="servio-chip">Telegram connected</span>
              ) : null}
            </div>
          ) : (
            <div className="servio-account-profile__notice">
              Session bridge ещё не отдал user context. Для действий остаётся доступен legacy account/login flow.
            </div>
          )}
        </section>

        <section className="servio-card servio-account-nav-wrap">
          <AccountNav />
        </section>
      </aside>

      <section className="servio-account__content">{children}</section>
    </div>
  );
}
