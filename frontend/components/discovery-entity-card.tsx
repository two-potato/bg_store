import Link from "next/link";

import { normalizeAssetUrl } from "@/lib/catalog-api";

type DiscoveryEntityCardProps = {
  href: string;
  kicker: string;
  title: string;
  copy: string;
  cta: string;
  image?: string | null;
  imageAlt: string;
  imageFit?: "cover" | "contain";
  fallback?: string;
  meta?: string[];
};

export function DiscoveryEntityCard({
  href,
  kicker,
  title,
  copy,
  cta,
  image,
  imageAlt,
  imageFit = "cover",
  fallback,
  meta = [],
}: DiscoveryEntityCardProps) {
  return (
    <article className="servio-discovery-card">
      <Link
        href={href}
        className={`servio-discovery-card__media ${imageFit === "contain" ? "is-contain" : ""}`}
      >
        {image ? (
          <img src={normalizeAssetUrl(image)} alt={imageAlt} className="servio-discovery-card__image" />
        ) : (
          <div className="servio-discovery-card__fallback">{(fallback || title).slice(0, 1).toUpperCase()}</div>
        )}
      </Link>

      <div className="servio-discovery-card__body">
        <span className="servio-link-card__eyebrow">{kicker}</span>
        <h2 className="servio-card-title">{title}</h2>
        <p className="servio-copy">{copy}</p>

        {meta.length ? (
          <div className="servio-discovery-card__meta">
            {meta.map((item) => (
              <span key={item} className="servio-chip servio-chip--compact">
                {item}
              </span>
            ))}
          </div>
        ) : null}

        <Link href={href} className="servio-button servio-button--secondary">
          {cta}
        </Link>
      </div>
    </article>
  );
}
