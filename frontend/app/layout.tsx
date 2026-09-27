import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "لجی‌راد | شبکه هوشمند حمل بین‌المللی",
  description: "یک درخواست، چند پیشنهاد قیمت معتبر از شرکت‌های حمل؛ مقایسه شفاف و اجرای قابل پیگیری.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap" rel="stylesheet" />
      </head>
      <body>
        <header className="top">
          <div className="container">
            <Link href="/" className="logo">Logi<span>rad</span></Link>
            <nav>
              <Link href="/#rfq">درخواست قیمت</Link>
              <Link href="/#calculator">ماشین‌حساب</Link>
              <Link href="/#track">پیگیری</Link>
              <Link href="/portal">شرکت‌های حمل</Link>
              <Link href="/ops">پنل عملیات</Link>
            </nav>
          </div>
        </header>
        {children}
        <footer>© Logirad — شبکه هوشمند لجستیک بین‌المللی</footer>
      </body>
    </html>
  );
}
