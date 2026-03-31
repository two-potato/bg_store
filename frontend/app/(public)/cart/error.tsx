"use client";

type CartErrorProps = {
  error: Error;
  reset: () => void;
};

export default function CartError({ error, reset }: CartErrorProps) {
  return (
    <section className="servio-card servio-account-state servio-account-state--danger" aria-live="assertive">
      <span className="servio-eyebrow">Cart error</span>
      <h1 className="servio-card-title">Не удалось загрузить cart surface</h1>
      <p className="servio-copy">
        {error.message || "Во время загрузки корзины произошла ошибка. Контур остановлен на безопасной границе."}
      </p>
      <div className="servio-actions">
        <button type="button" className="servio-button servio-button--secondary" onClick={reset}>
          Повторить
        </button>
      </div>
    </section>
  );
}
