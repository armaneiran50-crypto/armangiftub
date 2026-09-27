import type { Metadata } from "next";
import Link from "next/link";
import { LANES } from "@/lib/lanes";

export const metadata: Metadata = {
  title: "مسیرهای حمل بین‌المللی | لجی‌راد",
  description: "راهنمای مسیرهای حمل از چین، ترکیه، هند و اروپا به امارات، عربستان، قطر و عمان؛ زمان تقریبی، مدارک و دریافت پیشنهاد قیمت.",
  alternates: { canonical: "/shipping" },
};

export default function ShippingIndex() {
  return (
    <main className="container">
      <section className="hero">
        <h1>مسیرهای حمل</h1>
        <p>برای هر مسیر: روش‌های حمل، زمان تقریبی، بنادر، مدارک و امکان دریافت چند پیشنهاد قیمت از شرکت‌های معتبر.</p>
      </section>
      <div className="steps">
        {LANES.map((l) => (
          <Link key={l.slug} href={`/shipping/${l.slug}`} className="step" style={{ color: "var(--text)" }}>
            <b>{l.originName} ← {l.destinationName}</b>
            <small>{l.description}</small>
          </Link>
        ))}
      </div>
      <p style={{ marginTop: 24 }}><Link href="/tools/cbm-calculator">ماشین‌حساب CBM و وزن قابل‌محاسبه ←</Link></p>
    </main>
  );
}
