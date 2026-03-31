import Link from "next/link";

export default function NotFound() {
  return (
    <section className="servio-card servio-not-found">
      <span className="servio-eyebrow">Route fallback</span>
      <h1 className="servio-page-title">Этот маршрут пока остаётся на Django-контуре</h1>
      <p className="servio-copy">
        Новый storefront уже обслуживает public surfaces, но transactional и кабинетные сценарии всё ещё
        специально закреплены за backend-first маршрутизацией до готовности API bridge.
      </p>
      <div className="servio-actions" style={{ justifyContent: "center" }}>
        <Link href="/" className="servio-button servio-button--primary">
          Вернуться на storefront home
        </Link>
      </div>
    </section>
  );
}
