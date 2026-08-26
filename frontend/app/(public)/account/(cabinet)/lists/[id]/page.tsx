import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { AccountBlocker } from "@/components/account/account-blocker";
import { SavedListDetailManager } from "@/components/account/saved-list-detail-manager";
import {
  BridgeApiError,
  getStorefrontSavedListDetail,
  getStorefrontSessionBootstrap,
} from "@/lib/buyer-account-api";
import { legacyStorefrontUrl, loginUrlWithNext } from "@/lib/storefront-bridge";

type SavedListDetailPageProps = {
  params: Promise<{ id: string }>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: SavedListDetailPageProps): Promise<Metadata> {
  const { id } = await params;
  return {
    title: `Список закупки #${id}`,
    description: "Детали buyer списка закупки в Next storefront.",
    robots: {
      index: false,
      follow: false,
    },
  };
}

const blockers = [
  "Без авторизованной browser session список закупки недоступен.",
  "Нужны контракты `/api/storefront/tools/lists/{id}/` и mutations remove-item/move-to-cart.",
  "Добавление позиций в список из каталога остаётся отдельной UX итерацией.",
];

export default async function SavedListDetailPage({ params }: SavedListDetailPageProps) {
  const { id } = await params;
  const listId = Number(id);

  if (!Number.isInteger(listId) || listId <= 0) {
    notFound();
  }

  let session;
  try {
    session = await getStorefrontSessionBootstrap();
  } catch {
    return (
      <AccountBlocker
        title={`Список #${listId} ждёт session bridge`}
        copy="Не удалось получить session bootstrap."
        blockers={blockers}
        ctaHref={legacyStorefrontUrl(`/lists/${listId}/`)}
        ctaLabel="Открыть legacy список"
      />
    );
  }

  if (!session.session.authenticated) {
    return (
      <AccountBlocker
        title="Для списка закупки нужна авторизация"
        copy="Пользователь не авторизован в browser session."
        blockers={blockers}
        ctaHref={loginUrlWithNext(session.urls.login, `/account/lists/${listId}`)}
        ctaLabel="Войти в аккаунт"
      />
    );
  }

  let detail;
  try {
    detail = await getStorefrontSavedListDetail(listId);
  } catch (error) {
    if (error instanceof BridgeApiError && error.status === 404) {
      notFound();
    }

    const loginUrl =
      error instanceof BridgeApiError && error.status === 401
        ? loginUrlWithNext(session.urls.login, `/account/lists/${listId}`)
        : legacyStorefrontUrl(`/lists/${listId}/`);

    return (
      <AccountBlocker
        title={`Не удалось загрузить список #${listId}`}
        copy="Bridge endpoint списка закупки временно недоступен."
        blockers={blockers}
        ctaHref={loginUrl}
        ctaLabel="Открыть legacy список"
      />
    );
  }

  return (
    <div className="servio-account-main">
      <section className="servio-card servio-card--hero">
        <span className="servio-eyebrow">List detail</span>
        <h1 className="servio-page-title">Список закупки #{detail.saved_list.id}</h1>
        <p className="servio-copy servio-copy--lead">
          Управление позициями списка и быстрый перенос в корзину на backend контрактах.
        </p>
      </section>
      <SavedListDetailManager
        listId={listId}
        initialDetail={detail.saved_list}
        csrfToken={session.session.csrf_token}
      />
    </div>
  );
}
