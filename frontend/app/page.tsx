import Calculator from "@/components/Calculator";
import RFQForm from "@/components/RFQForm";
import Track from "@/components/Track";
import WhatsAppButton from "@/components/WhatsAppButton";

const STEPS = [
  ["۱. یک درخواست", "مسیر، بار و زمان را یک‌بار ثبت کنید"],
  ["۲. انتخاب هوشمند", "شرکت‌های معتبر همان مسیر انتخاب می‌شوند"],
  ["۳. مقایسه شفاف", "کرایه، هزینه‌های مبدأ و مقصد، زمان ترانزیت"],
  ["۴. رزرو و پیگیری", "اسناد و وضعیت محموله در یک‌جا"],
];

export default function Home() {
  return (
    <main className="container">
      <section className="hero">
        <h1>یک درخواست، چند پیشنهاد حمل معتبر</h1>
        <p>لجی‌راد درخواست حمل شما را به شبکه‌ای از شرکت‌های حمل بین‌المللی می‌فرستد و پیشنهادها را به‌صورت قابل مقایسه در اختیارتان می‌گذارد؛ از چین، ترکیه، هند و اروپا به کشورهای حاشیه خلیج فارس.</p>
        <div className="steps">
          {STEPS.map(([t, d]) => (<div className="step" key={t}><b>{t}</b><small>{d}</small></div>))}
        </div>
      </section>
      <div className="cols">
        <RFQForm />
        <div>
          <Calculator />
          <Track />
        </div>
      </div>
      <WhatsAppButton />
    </main>
  );
}
