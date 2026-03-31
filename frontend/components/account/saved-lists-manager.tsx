"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";
import type { BridgeSavedListSummary } from "@/lib/buyer-account-api";

type SavedListsManagerProps = {
  initialLists: BridgeSavedListSummary[];
  csrfToken: string;
};

type ListFormState = {
  name: string;
  description: string;
};

const emptyForm: ListFormState = {
  name: "",
  description: "",
};

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Moscow",
  }).format(parsed);
}

export function SavedListsManager({ initialLists, csrfToken }: SavedListsManagerProps) {
  const [lists, setLists] = useState(initialLists);
  const [form, setForm] = useState<ListFormState>(emptyForm);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function refreshLists() {
    const response = await fetch("/api/storefront/tools/lists/", {
      method: "GET",
      credentials: "include",
      headers: { accept: "application/json" },
    });
    const payload = (await response.json()) as {
      ok: boolean;
      saved_lists: BridgeSavedListSummary[];
    };
    if (response.ok && payload.ok) {
      setLists(payload.saved_lists);
    }
  }

  async function createList(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/storefront/tools/lists/", {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify(form),
      });
      const payload = (await response.json()) as {
        ok: boolean;
        error?: string;
        saved_list?: { id: number };
      };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось создать список.");
        return;
      }
      void trackBuyerWaveEvent("saved_list_created", "saved_lists", {
        list_id: payload.saved_list?.id || null,
      });
      await refreshLists();
      setForm(emptyForm);
      setSuccess("Список закупки создан.");
    } catch {
      setError("Сетевая ошибка при создании списка.");
    } finally {
      setPending(false);
    }
  }

  async function togglePublic(listId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/storefront/tools/lists/${listId}/toggle-public/`, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({}),
      });
      const payload = (await response.json()) as { ok: boolean; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось обновить публичность списка.");
        return;
      }
      await refreshLists();
      setSuccess("Публичность списка обновлена.");
    } catch {
      setError("Сетевая ошибка при обновлении списка.");
    } finally {
      setPending(false);
    }
  }

  async function moveToCart(listId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/storefront/tools/lists/${listId}/move-to-cart/`, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({}),
      });
      const payload = (await response.json()) as { ok: boolean; moved_items?: number; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось переместить список в корзину.");
        return;
      }
      void trackBuyerWaveEvent("saved_list_moved_to_cart", "saved_lists", {
        list_id: listId,
        moved_items: payload.moved_items || 0,
      });
      setSuccess(`В корзину добавлено позиций: ${payload.moved_items || 0}.`);
    } catch {
      setError("Сетевая ошибка при переносе списка в корзину.");
    } finally {
      setPending(false);
    }
  }

  async function deleteList(listId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/storefront/tools/lists/${listId}/delete/`, {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify({}),
      });
      const payload = (await response.json()) as { ok: boolean; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось удалить список.");
        return;
      }
      void trackBuyerWaveEvent("saved_list_deleted", "saved_lists", {
        list_id: listId,
      });
      await refreshLists();
      setSuccess("Список удалён.");
    } catch {
      setError("Сетевая ошибка при удалении списка.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="servio-account-two-col" aria-live="polite">
      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Списки закупки</h2>
        </div>

        {error ? <p className="servio-cart-summary__error">{error}</p> : null}
        {success ? <p className="servio-account-success">{success}</p> : null}

        {lists.length ? (
          <div className="servio-account-order-list">
            {lists.map((savedList) => (
              <article key={savedList.id} className="servio-account-order-row">
                <div className="servio-account-order-row__main">
                  <strong>{savedList.name}</strong>
                  <span>{savedList.description || "Без описания"}</span>
                  <span>{formatDateTime(savedList.updated_at)}</span>
                </div>
                <div className="servio-account-order-row__meta">
                  <span className="servio-chip">{savedList.items_count} поз.</span>
                  <span className="servio-chip">{savedList.is_public ? "Публичный" : "Приватный"}</span>
                  <Link href={`/account/lists/${savedList.id}`} className="servio-button servio-button--secondary">
                    Открыть
                  </Link>
                  <button
                    type="button"
                    className="servio-button servio-button--ghost"
                    onClick={() => togglePublic(savedList.id)}
                    disabled={pending}
                  >
                    Публичность
                  </button>
                  <button
                    type="button"
                    className="servio-button servio-button--ghost"
                    onClick={() => moveToCart(savedList.id)}
                    disabled={pending}
                  >
                    В корзину
                  </button>
                  <button
                    type="button"
                    className="servio-button servio-button--ghost"
                    onClick={() => deleteList(savedList.id)}
                    disabled={pending}
                  >
                    Удалить
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="servio-copy">
            Списков пока нет. Создайте первый список для повторяемых закупок и быстрых переносов в корзину.
          </p>
        )}
      </section>

      <section className="servio-card servio-card--soft">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Новый список</h2>
        </div>
        <form className="servio-form" onSubmit={createList}>
          <div className="servio-form-grid">
            <label className="servio-form-field">
              <span>Название</span>
              <input
                type="text"
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                required
              />
            </label>

            <label className="servio-form-field servio-form-field--wide">
              <span>Описание</span>
              <textarea
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              />
            </label>
          </div>
          <div className="servio-actions">
            <button type="submit" className="servio-button servio-button--primary" disabled={pending}>
              {pending ? "Сохраняем..." : "Создать список"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
