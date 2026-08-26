"use client";

import { useState, type FormEvent } from "react";

import type {
  BridgeAccountPreferences,
  BridgeValidationErrorPayload,
} from "@/lib/buyer-account-api";

type AccountPreferencesFormProps = {
  initialPreferences: BridgeAccountPreferences;
  csrfToken: string;
};

export function AccountPreferencesForm({
  initialPreferences,
  csrfToken,
}: AccountPreferencesFormProps) {
  const [preferences, setPreferences] = useState(initialPreferences);
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setSuccess("");
    setError("");

    try {
      const response = await fetch("/api/storefront/account/preferences/", {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify(preferences),
      });

      const payload = (await response.json()) as
        | { ok: true; preferences: BridgeAccountPreferences }
        | BridgeValidationErrorPayload
        | { ok: false; error?: string };

      if (!response.ok || !payload.ok) {
        if ("non_field_errors" in payload && payload.non_field_errors?.length) {
          setError(payload.non_field_errors.join(" "));
        } else {
          setError(("error" in payload && payload.error) || "Не удалось сохранить preferences.");
        }
        return;
      }

      setPreferences(payload.preferences);
      setSuccess("Предпочтения уведомлений сохранены.");
    } catch {
      setError("Сетевая ошибка при сохранении preferences.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="servio-form" onSubmit={handleSubmit} aria-live="polite">
      <div className="servio-toggle-list">
        <label className="servio-toggle">
          <input
            type="checkbox"
            checked={preferences.notify_email_orders}
            onChange={(event) =>
              setPreferences((prev) => ({
                ...prev,
                notify_email_orders: event.target.checked,
              }))
            }
          />
          <span>Email: статусы заказов и документы</span>
        </label>
        <label className="servio-toggle">
          <input
            type="checkbox"
            checked={preferences.notify_email_marketing}
            onChange={(event) =>
              setPreferences((prev) => ({
                ...prev,
                notify_email_marketing: event.target.checked,
              }))
            }
          />
          <span>Email: маркетинг и подборки</span>
        </label>
        <label className="servio-toggle">
          <input
            type="checkbox"
            checked={preferences.notify_telegram_orders}
            onChange={(event) =>
              setPreferences((prev) => ({
                ...prev,
                notify_telegram_orders: event.target.checked,
              }))
            }
          />
          <span>Telegram: статусы заказов</span>
        </label>
        <label className="servio-toggle">
          <input
            type="checkbox"
            checked={preferences.notify_telegram_marketing}
            onChange={(event) =>
              setPreferences((prev) => ({
                ...prev,
                notify_telegram_marketing: event.target.checked,
              }))
            }
          />
          <span>Telegram: маркетинговые уведомления</span>
        </label>
      </div>

      {!preferences.telegram_linked ? (
        <p className="servio-account-profile__notice">
          Telegram не привязан: telegram-уведомления сохранятся, но не будут доставляться до подключения.
        </p>
      ) : null}

      {error ? <p className="servio-cart-summary__error">{error}</p> : null}
      {success ? <p className="servio-account-success">{success}</p> : null}

      <div className="servio-actions">
        <button type="submit" className="servio-button servio-button--primary" disabled={pending}>
          {pending ? "Сохраняем..." : "Сохранить preferences"}
        </button>
      </div>
    </form>
  );
}
