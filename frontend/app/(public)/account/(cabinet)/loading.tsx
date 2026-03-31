export default function AccountLoading() {
  return (
    <div className="servio-account-loading" aria-live="polite">
      <section className="servio-card servio-account-skeleton">
        <span className="servio-eyebrow">Загрузка</span>
        <h1 className="servio-card-title">Подготавливаем buyer workspace</h1>
        <div className="servio-account-skeleton__row" />
        <div className="servio-account-skeleton__row" />
        <div className="servio-account-skeleton__row is-short" />
      </section>
    </div>
  );
}
