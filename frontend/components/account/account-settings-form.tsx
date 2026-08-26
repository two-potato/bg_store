"use client";

import { useState, type FormEvent } from "react";

import type {
  BridgeAccountSettings,
  BridgeValidationErrorPayload,
} from "@/lib/buyer-account-api";

type AccountSettingsFormProps = {
  initialSettings: BridgeAccountSettings;
  csrfToken: string;
};

type SettingsState = {
  full_name: string;
  contact_email: string;
  phone: string;
};

export function AccountSettingsForm({
  initialSettings,
  csrfToken,
}: AccountSettingsFormProps) {
  const [form, setForm] = useState<SettingsState>({
    full_name: initialSettings.full_name || "",
    contact_email: initialSettings.contact_email || "",
    phone: initialSettings.phone || "",
  });
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setSuccess("");
    setError("");
    setFieldErrors({});

    try {
      const response = await fetch("/api/storefront/account/settings/", {
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

      const payload = (await response.json()) as
        | { ok: true; settings: BridgeAccountSettings }
        | BridgeValidationErrorPayload
        | { ok: false; error?: string };

      if (!response.ok || !payload.ok) {
        if ("fields" in payload && payload.fields) {
          setFieldErrors(payload.fields);
        }
        if ("non_field_errors" in payload && payload.non_field_errors?.length) {
          setError(payload.non_field_errors.join(" "));
        } else {
          setError(("error" in payload && payload.error) || "Не удалось сохранить настройки.");
        }
        return;
      }

      setForm({
        full_name: payload.settings.full_name || "",
        contact_email: payload.settings.contact_email || "",
        phone: payload.settings.phone || "",
      });
      setSuccess("Настройки профиля сохранены.");
    } catch {
      setError("Сетевая ошибка при сохранении настроек.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="servio-form" onSubmit={handleSubmit} aria-live="polite">
      <div className="servio-form-grid">
        <label className="servio-form-field">
          <span>Имя и фамилия</span>
          <input
            type="text"
            value={form.full_name}
            onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
          />
          {fieldErrors.full_name?.length ? <small>{fieldErrors.full_name[0]}</small> : null}
        </label>

        <label className="servio-form-field">
          <span>Email</span>
          <input
            type="email"
            value={form.contact_email}
            onChange={(event) => setForm((prev) => ({ ...prev, contact_email: event.target.value }))}
          />
          {fieldErrors.contact_email?.length ? <small>{fieldErrors.contact_email[0]}</small> : null}
        </label>

        <label className="servio-form-field">
          <span>Телефон</span>
          <input
            type="text"
            value={form.phone}
            onChange={(event) => setForm((prev) => ({ ...prev, phone: event.target.value }))}
          />
          {fieldErrors.phone?.length ? <small>{fieldErrors.phone[0]}</small> : null}
        </label>
      </div>

      {error ? <p className="servio-cart-summary__error">{error}</p> : null}
      {success ? <p className="servio-account-success">{success}</p> : null}

      <div className="servio-actions">
        <button type="submit" className="servio-button servio-button--primary" disabled={pending}>
          {pending ? "Сохраняем..." : "Сохранить"}
        </button>
      </div>
    </form>
  );
}
