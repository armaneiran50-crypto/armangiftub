import type { Metadata } from "next";
import Link from "next/link";
import Calculator from "@/components/Calculator";

export const metadata: Metadata = {
  title: "ماشین‌حساب CBM و وزن قابل‌محاسبه (هوایی، دریایی، زمینی) | لجی‌راد",
  description: "حجم بار (متر مکعب)، وزن حجمی و وزن مبنای کرایه را برای حمل هوایی، دریایی LCL/FCL و زمینی محاسبه کنید.",
  alternates: { canonical: "/tools/cbm-calculator" },
};

export default function CbmTool() {
  return (
    <main className="container">
      <section className="hero">
        <h1>ماشین‌حساب CBM و وزن قابل‌محاسبه</h1>
        <p>شرکت‌های حمل کرایه را بر اساس بیشترِ «وزن واقعی» و «وزن حجمی» محاسبه می‌کنند. ابعاد بسته‌ها را وارد کنید تا مبنای کرایه را ببینید.</p>
      </section>
      <div className="cols">
        <Calculator />
        <div className="card">
          <h2>ضریب‌ها چطور محاسبه می‌شوند؟</h2>
          <ul>
            <li><b>هوایی:</b> هر متر مکعب معادل ۱۶۷ کیلوگرم (ضریب ۶۰۰۰ IATA).</li>
            <li><b>زمینی:</b> هر متر مکعب معادل ۳۳۳ کیلوگرم (ضریب رایج ۳۰۰۰).</li>
            <li><b>دریایی LCL:</b> هر متر مکعب یا هر ۱۰۰۰ کیلوگرم یک «Revenue Ton»؛ هر کدام بیشتر باشد.</li>
          </ul>
          <p className="muted">ضریب‌ها ممکن است بین شرکت‌ها کمی متفاوت باشد؛ در پیشنهاد قیمت ذکر می‌شود.</p>
          <p><Link href="/#rfq">درخواست قیمت با همین مشخصات ←</Link></p>
        </div>
      </div>
    </main>
  );
}
