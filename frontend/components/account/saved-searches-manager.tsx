"use client";

import { useState, type FormEvent } from "react";

import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";
import type { BridgeSavedSearch } from "@/lib/buyer-account-api";

type SavedSearchesManagerProps = {
  initialSearches: BridgeSavedSearch[];
  csrfToken: string;
};

type SearchFormState = {
  name: string;
  querystring: string;
};

const emptyForm: SearchFormState = {
  name: "",
  querystring: "",
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

export function SavedSearchesManager({ initialSearches, csrfToken }: SavedSearchesManagerProps) {
  const [searches, setSearches] = useState(initialSearches);
  const [form, setForm] = useState<SearchFormState>(emptyForm);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function refreshSearches() {
    const response = await fetch("/api/storefront/tools/saved-searches/", {
      method: "GET",
      credentials: "include",
      headers: { accept: "application/json" },
    });
    const payload = (await response.json()) as {
      ok: boolean;
      saved_searches: BridgeSavedSearch[];
    };
    if (response.ok && payload.ok) {
      setSearches(payload.saved_searches);
    }
  }

  async function createSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/storefront/tools/saved-searches/", {
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
        saved_search?: { id: number; querystring: string };
      };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось сохранить поиск.");
        return;
      }
      void trackBuyerWaveEvent("saved_search_saved", "saved_searches", {
        search_id: payload.saved_search?.id || null,
      });
      await refreshSearches();
      setForm(emptyForm);
      setSuccess("Поиск сохранён.");
    } catch {
      setError("Сетевая ошибка при сохранении поиска.");
    } finally {
      setPending(false);
    }
  }

  async function deleteSearch(searchId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/api/storefront/tools/saved-searches/${searchId}/delete/`, {
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
        setError(payload.error || "Не удалось удалить поиск.");
        return;
      }
      void trackBuyerWaveEvent("saved_search_deleted", "saved_searches", {
        search_id: searchId,
      });
      await refreshSearches();
      setSuccess("Поиск удалён.");
    } catch {
      setError("Сетевая ошибка при удалении поиска.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="servio-account-two-col" aria-live="polite">
      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Сохранённые поиски</h2>
        </div>

        {error ? <p className="servio-cart-summary__error">{error}</p> : null}
        {success ? <p className="servio-account-success">{success}</p> : null}

        {searches.length ? (
          <div className="servio-account-order-list">
            {searches.map((search) => (
              <article key={search.id} className="servio-account-order-row">
                <div className="servio-account-order-row__main">
                  <strong>{search.name}</strong>
                  <span>{search.querystring}</span>
                  <span>{formatDateTime(search.created_at)}</span>
                </div>
                <div className="servio-account-order-row__meta">
                  <a href={`/search?${search.querystring}`} className="servio-button servio-button--secondary">
                    Открыть поиск
                  </a>
                  <button
                    type="button"
                    className="servio-button servio-button--ghost"
                    onClick={() => deleteSearch(search.id)}
                    disabled={pending}
                  >
                    Удалить
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="servio-copy">Сохранённых поисков пока нет.</p>
        )}
      </section>

      <section className="servio-card servio-card--soft">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Сохранить новый поиск</h2>
        </div>
        <form className="servio-form" onSubmit={createSearch}>
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
              <span>Query string</span>
              <input
                type="text"
                value={form.querystring}
                onChange={(event) => setForm((prev) => ({ ...prev, querystring: event.target.value }))}
                placeholder="q=кофе&brand=12"
                required
              />
            </label>
          </div>
          <div className="servio-actions">
            <button type="submit" className="servio-button servio-button--primary" disabled={pending}>
              {pending ? "Сохраняем..." : "Сохранить поиск"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
