"use client";

import { useMemo, useState, type FormEvent } from "react";

import { trackBuyerWaveEvent } from "@/lib/buyer-wave-analytics";
import type {
  BridgeAccountAddress,
  BridgeValidationErrorPayload,
} from "@/lib/buyer-account-api";

type AccountAddressesManagerProps = {
  initialAddresses: BridgeAccountAddress[];
  legalEntities: Array<{ id: number; name: string }>;
  csrfToken: string;
};

type AddressFormState = {
  legal_entity: string;
  label: string;
  country: string;
  city: string;
  street: string;
  postcode: string;
  details: string;
  is_default: boolean;
};

const emptyForm: AddressFormState = {
  legal_entity: "",
  label: "",
  country: "Россия",
  city: "",
  street: "",
  postcode: "",
  details: "",
  is_default: false,
};

export function AccountAddressesManager({
  initialAddresses,
  legalEntities,
  csrfToken,
}: AccountAddressesManagerProps) {
  const [addresses, setAddresses] = useState(initialAddresses);
  const [form, setForm] = useState<AddressFormState>(() => {
    const firstEntityId =
      legalEntities[0]?.id ?? initialAddresses[0]?.legal_entity.id;
    return { ...emptyForm, legal_entity: firstEntityId ? String(firstEntityId) : "" };
  });
  const [pending, setPending] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const availableLegalEntities = useMemo(() => {
    if (legalEntities.length) {
      return legalEntities;
    }
    const map = new Map<number, string>();
    for (const address of addresses) {
      map.set(address.legal_entity.id, address.legal_entity.name);
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [addresses, legalEntities]);
  const canCreateAddress = availableLegalEntities.length > 0;

  async function refreshAddresses() {
    const response = await fetch("/api/storefront/account/addresses/", {
      method: "GET",
      credentials: "include",
      headers: { accept: "application/json" },
    });
    const payload = (await response.json()) as { ok: boolean; addresses: BridgeAccountAddress[] };
    if (response.ok && payload.ok) {
      setAddresses(payload.addresses);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFieldErrors({});
    setError("");
    setSuccess("");

    try {
      const body = {
        ...form,
        legal_entity: Number(form.legal_entity),
      };
      const response = await fetch("/api/storefront/account/addresses/", {
        method: "POST",
        credentials: "include",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "x-csrftoken": csrfToken,
          "x-requested-with": "XMLHttpRequest",
        },
        body: JSON.stringify(body),
      });

      const payload = (await response.json()) as
        | { ok: true; address: BridgeAccountAddress }
        | BridgeValidationErrorPayload
        | { ok: false; error?: string };

      if (!response.ok || !payload.ok) {
        if ("fields" in payload && payload.fields) {
          setFieldErrors(payload.fields);
        }
        if ("non_field_errors" in payload && payload.non_field_errors?.length) {
          setError(payload.non_field_errors.join(" "));
        } else {
          setError(("error" in payload && payload.error) || "Не удалось добавить адрес.");
        }
        return;
      }

      void trackBuyerWaveEvent("address_created", "account_addresses", {
        address_id: payload.address.id,
        legal_entity_id: payload.address.legal_entity.id,
      });
      await refreshAddresses();
      setForm((prev) => ({ ...emptyForm, legal_entity: prev.legal_entity || "" }));
      setSuccess("Адрес добавлен.");
    } catch {
      setError("Сетевая ошибка при добавлении адреса.");
    } finally {
      setPending(false);
    }
  }

  async function setDefault(addressId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(
        `/api/storefront/account/addresses/${addressId}/default/`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            accept: "application/json",
            "content-type": "application/json",
            "x-csrftoken": csrfToken,
            "x-requested-with": "XMLHttpRequest",
          },
          body: JSON.stringify({}),
        },
      );

      const payload = (await response.json()) as { ok: boolean; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось назначить адрес по умолчанию.");
        return;
      }
      await refreshAddresses();
      setSuccess("Адрес по умолчанию обновлён.");
    } catch {
      setError("Сетевая ошибка при обновлении адреса.");
    } finally {
      setPending(false);
    }
  }

  async function deleteAddress(addressId: number) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(
        `/api/storefront/account/addresses/${addressId}/delete/`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            accept: "application/json",
            "content-type": "application/json",
            "x-csrftoken": csrfToken,
            "x-requested-with": "XMLHttpRequest",
          },
          body: JSON.stringify({}),
        },
      );

      const payload = (await response.json()) as { ok: boolean; error?: string };
      if (!response.ok || !payload.ok) {
        setError(payload.error || "Не удалось удалить адрес.");
        return;
      }
      await refreshAddresses();
      setSuccess("Адрес удалён.");
    } catch {
      setError("Сетевая ошибка при удалении адреса.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="servio-account-two-col">
      <section className="servio-card">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Адреса доставки</h2>
        </div>

        {addresses.length ? (
          <div className="servio-account-order-list">
            {addresses.map((address) => (
              <article key={address.id} className="servio-account-order-row">
                <div className="servio-account-order-row__main">
                  <strong>
                    {address.label} {address.is_default ? "(по умолчанию)" : ""}
                  </strong>
                  <span>
                    {address.country}, {address.city}, {address.street}
                  </span>
                  <span>Юрлицо: {address.legal_entity.name}</span>
                </div>
                <div className="servio-account-order-row__meta">
                  {!address.is_default ? (
                    <button
                      type="button"
                      className="servio-button servio-button--secondary"
                      onClick={() => setDefault(address.id)}
                      disabled={pending}
                    >
                      Сделать default
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="servio-button servio-button--ghost"
                    onClick={() => deleteAddress(address.id)}
                    disabled={pending}
                  >
                    Удалить
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="servio-copy">Адресов пока нет. Добавьте первый адрес для checkout/B2B flow.</p>
        )}
      </section>

      <section className="servio-card servio-card--soft">
        <div className="servio-account-section-head">
          <h2 className="servio-card-title">Добавить адрес</h2>
        </div>
        {!canCreateAddress ? (
          <p className="servio-account-profile__notice">
            Нет доступных юрлиц для привязки адреса. Сначала добавьте компанию в разделе «Компании».
          </p>
        ) : null}
        <form className="servio-form" onSubmit={handleCreate} aria-live="polite">
          <div className="servio-form-grid">
            <label className="servio-form-field">
              <span>Юрлицо</span>
              <select
                value={form.legal_entity}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, legal_entity: event.target.value }))
                }
                disabled={!canCreateAddress}
              >
                <option value="">Выберите юрлицо</option>
                {availableLegalEntities.map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.name}
                  </option>
                ))}
              </select>
              {fieldErrors.legal_entity?.length ? <small>{fieldErrors.legal_entity[0]}</small> : null}
            </label>

            <label className="servio-form-field">
              <span>Название</span>
              <input
                type="text"
                value={form.label}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, label: event.target.value }))
                }
              />
              {fieldErrors.label?.length ? <small>{fieldErrors.label[0]}</small> : null}
            </label>

            <label className="servio-form-field">
              <span>Страна</span>
              <input
                type="text"
                value={form.country}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, country: event.target.value }))
                }
              />
            </label>

            <label className="servio-form-field">
              <span>Город</span>
              <input
                type="text"
                value={form.city}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, city: event.target.value }))
                }
              />
              {fieldErrors.city?.length ? <small>{fieldErrors.city[0]}</small> : null}
            </label>

            <label className="servio-form-field">
              <span>Улица</span>
              <input
                type="text"
                value={form.street}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, street: event.target.value }))
                }
              />
              {fieldErrors.street?.length ? <small>{fieldErrors.street[0]}</small> : null}
            </label>

            <label className="servio-form-field">
              <span>Почтовый индекс</span>
              <input
                type="text"
                value={form.postcode}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, postcode: event.target.value }))
                }
              />
            </label>

            <label className="servio-form-field servio-form-field--wide">
              <span>Комментарий</span>
              <textarea
                value={form.details}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, details: event.target.value }))
                }
              />
            </label>

            <label className="servio-toggle">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, is_default: event.target.checked }))
                }
              />
              <span>Сделать адресом по умолчанию</span>
            </label>
          </div>

          {error ? <p className="servio-cart-summary__error">{error}</p> : null}
          {success ? <p className="servio-account-success">{success}</p> : null}

          <div className="servio-actions">
            <button type="submit" className="servio-button servio-button--primary" disabled={pending || !canCreateAddress}>
              {pending ? "Сохраняем..." : "Добавить адрес"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
