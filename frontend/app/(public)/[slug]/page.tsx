import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { PageSections } from "@/components/page-sections";
import { marketingPages, marketingPageSlugs } from "@/lib/marketing-pages";

type MarketingPageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateStaticParams() {
  return marketingPageSlugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: MarketingPageProps["params"];
}): Promise<Metadata> {
  const { slug } = await params;
  const page = marketingPages[slug];

  if (!page) {
    return {};
  }

  return {
    title: page.title,
    description: page.description,
  };
}

export default async function MarketingPage({
  params,
}: MarketingPageProps) {
  const { slug } = await params;
  const page = marketingPages[slug];

  if (!page) {
    notFound();
  }

  return (
    <div className="servio-grid servio-grid--page">
      <section className="servio-page-hero">
        <div className="servio-card servio-card--hero">
          <span className="servio-eyebrow">{page.eyebrow}</span>
          <p className="servio-kicker">{page.lead}</p>
          <h1 className="servio-page-title">{page.title}</h1>
          <p className="servio-copy servio-copy--lead">{page.intro}</p>
        </div>
        <aside className="servio-card servio-card--soft">
          <span className="servio-eyebrow">Page signals</span>
          <ul className="servio-metric-list servio-metric-list--compact">
            {page.metrics.map((metric, index) => (
              <li
                key={metric.label}
                className="servio-metric servio-metric--soft"
                style={{ animationDelay: `${index * 80}ms` }}
              >
                <strong>{metric.value}</strong>
                <span>{metric.label}</span>
              </li>
            ))}
          </ul>
        </aside>
      </section>

      <div className="servio-notice servio-notice--strong">{page.notice}</div>
      <PageSections sections={page.sections} />

      <section className="servio-related">
        <div className="servio-related__header">
          <span className="servio-eyebrow">Next routes</span>
          <h2 className="servio-card-title">Связанные public surfaces</h2>
        </div>
        <div className="servio-mini-grid">
          {page.related.map((link, index) => (
            <Link
              key={link.href}
              href={link.href}
              className="servio-link-card"
              style={{ animationDelay: `${160 + index * 80}ms` }}
            >
              <span className="servio-link-card__eyebrow">{link.label}</span>
              <strong>{link.caption}</strong>
              <span>Открыть маршрут</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
