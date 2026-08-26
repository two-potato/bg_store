"use client";

type AccountErrorProps = {
  error: Error;
  reset: () => void;
};

export default function AccountError({ error, reset }: AccountErrorProps) {
  return (
    <section className="servio-card servio-account-state servio-account-state--danger" aria-live="assertive">
      <span className="servio-eyebrow">Ошибка</span>
      <h1 className="servio-card-title">Не удалось загрузить buyer surface</h1>
      <p className="servio-copy">
        {error.message || "Во время загрузки account/orders произошла ошибка. Контур migration остановлен на безопасной границе."}
      </p>
      <div className="servio-actions">
        <button type="button" className="servio-button servio-button--secondary" onClick={reset}>
          Повторить
        </button>
      </div>
    </section>
  );
}
