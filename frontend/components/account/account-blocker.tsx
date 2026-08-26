type AccountBlockerProps = {
  title: string;
  copy: string;
  blockers: string[];
  ctaHref?: string;
  ctaLabel?: string;
};

export function AccountBlocker({
  title,
  copy,
  blockers,
  ctaHref,
  ctaLabel,
}: AccountBlockerProps) {
  return (
    <section className="servio-card servio-account-state servio-account-state--warning" aria-live="polite">
      <span className="servio-eyebrow">Migration boundary</span>
      <h1 className="servio-card-title">{title}</h1>
      <p className="servio-copy">{copy}</p>
      <ul className="servio-account-state__list">
        {blockers.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {ctaHref && ctaLabel ? (
        <div className="servio-actions">
          <a href={ctaHref} className="servio-button servio-button--primary">
            {ctaLabel}
          </a>
        </div>
      ) : null}
    </section>
  );
}
