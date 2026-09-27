import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import LaneStats from "@/components/LaneStats";
import RFQForm from "@/components/RFQForm";
import { MODES } from "@/lib/labels";
import { LANES, laneBySlug } from "@/lib/lanes";
import { SITE_URL } from "@/lib/site";

export const dynamicParams = false;

export function generateStaticParams() {
  return LANES.map((l) => ({ slug: l.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const lane = laneBySlug((await params).slug);
  if (!lane) return {};
  return {
    title: `${lane.title} | لجی‌راد`,
    description: lane.description,
    alternates: { canonical: `/shipping/${lane.slug}` },
    // Pages stay out of the index until reviewed (masterplan §15: no thin pages).
    robots: lane.reviewed ? { index: true, follow: true } : { index: false, follow: true },
    openGraph: { title: lane.title, description: lane.description, url: `/shipping/${lane.slug}`, type: "article" },
  };
}

export default async function LanePage({ params }: { params: Promise<{ slug: string }> }) {
  const lane = laneBySlug((await params).slug);
  if (!lane) notFound();
  const firstMode = lane.modes[0].mode;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      { "@type": "Service", name: lane.title, serviceType: "Freight forwarding marketplace", description: lane.description,
        areaServed: [lane.originName, lane.destinationName], provider: { "@type": "Organization", name: "Logirad", url: SITE_URL } },
      { "@type": "FAQPage", mainEntity: lane.faq.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) },
      { "@type": "BreadcrumbList", itemListElement: [
        { "@type": "ListItem", position: 1, name: "لجی‌راد", item: SITE_URL },
        { "@type": "ListItem", position: 2, name: "مسیرها", item: `${SITE_URL}/shipping` },
        { "@type": "ListItem", position: 3, name: lane.title, item: `${SITE_URL}/shipping/${lane.slug}` } ] },
    ],
  };
  const others = LANES.filter((l) => l.slug !== lane.slug && (l.origin === lane.origin || l.destination === lane.destination));

  return (
    <main className="container">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <nav className="muted" style={{ paddingTop: 20, fontSize: 14 }} aria-label="breadcrumb">
        <Link href="/">خانه</Link> / <Link href="/shipping">مسیرها</Link> / {lane.originName} به {lane.destinationName}
      </nav>
      <section className="hero" style={{ paddingTop: 16 }}>
        <h1>{lane.title}</h1>
        <p>{lane.intro}</p>
        <div className="actions"><a href="#rfq"><button>دریافت چند پیشنهاد قیمت برای این مسیر</button></a></div>
      </section>

      <div className="cols">
        <div>
          <div className="card">
            <h2>روش‌های حمل و زمان تقریبی</h2>
            <p className="sub">زمان‌ها تقریبی‌اند و به سرویس، فصل و شرایط مسیر بستگی دارند؛ زمان دقیق در هر پیشنهاد قیمت ذکر می‌شود.</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>روش</th><th>زمان تقریبی</th><th>نکته</th></tr></thead>
                <tbody>{lane.modes.map((m) => <tr key={m.mode}><td>{MODES[m.mode]}</td><td>{m.transit}</td><td className="muted">{m.note || "—"}</td></tr>)}</tbody>
              </table>
            </div>
          </div>
          <div className="card">
            <h2>بنادر و فرودگاه‌های اصلی</h2>
            <div className="grid">
              <div><h3>مبدأ ({lane.originName})</h3><ul>{lane.ports.origin.map((p) => <li key={p} className="ltr" style={{ textAlign: "start" }}>{p}</li>)}</ul></div>
              <div><h3>مقصد ({lane.destinationName})</h3><ul>{lane.ports.destination.map((p) => <li key={p}>{p}</li>)}</ul></div>
            </div>
          </div>
          <div className="card">
            <h2>مدارک معمول</h2>
            <ul>{lane.documents.map((d) => <li key={d}>{d}</li>)}</ul>
            <p className="muted" style={{ fontSize: 13 }}>الزامات دقیق به نوع کالا و قوانین کشور مقصد بستگی دارد و باید با ترخیص‌کار تأیید شود.</p>
          </div>
          <div className="card">
            <h2>نکات کاربردی</h2>
            <ul>{lane.tips.map((t) => <li key={t}>{t}</li>)}</ul>
            <p><Link href="/tools/cbm-calculator">محاسبه حجم و وزن قابل‌محاسبه بار ←</Link></p>
          </div>
          <LaneStats origin={lane.origin} destination={lane.destination} />
          <div className="card">
            <h2>پرسش‌های متداول</h2>
            {lane.faq.map((f) => (<details key={f.q} style={{ marginBottom: 8 }}><summary><b>{f.q}</b></summary><p>{f.a}</p></details>))}
          </div>
        </div>
        <div>
          <RFQForm initial={{ origin_country: lane.origin, destination_country: lane.destination, mode: firstMode }} />
          {others.length > 0 && (
            <div className="card">
              <h2>مسیرهای مرتبط</h2>
              <ul>{others.map((o) => <li key={o.slug}><Link href={`/shipping/${o.slug}`}>{o.title}</Link></li>)}</ul>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
