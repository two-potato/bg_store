export type MarketingSection = {
  title: string;
  body: string;
  tag?: string;
  points?: string[];
  emphasis?: string;
};

export function PageSections({ sections }: { sections: MarketingSection[] }) {
  return (
    <div className="servio-section-grid">
      {sections.map((section, index) => (
        <section
          key={section.title}
          className="servio-section"
          style={{ animationDelay: `${index * 90}ms` }}
        >
          <div className="servio-section__head">
            {section.tag ? <span className="servio-section__tag">{section.tag}</span> : null}
            <h2>{section.title}</h2>
          </div>
          <p>{section.body}</p>
          {section.emphasis ? <p className="servio-section__emphasis">{section.emphasis}</p> : null}
          {section.points?.length ? (
            <ul className="servio-point-list">
              {section.points.map((point) => (
                <li key={point} className="servio-point">
                  {point}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ))}
    </div>
  );
}
