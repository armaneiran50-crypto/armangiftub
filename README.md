# Logirad — شبکه هوشمند لجستیک بین‌المللی

MVP پلتفرم بر اساس «نقشه اجرایی جامع پلتفرم هوشمند لجستیک» (نسخه ۱.۰): صاحب کالا یک درخواست (RFQ) ثبت می‌کند،
پلتفرم آن را به شرکت‌های حمل منطبق می‌فرستد، پیشنهادها یکسان‌سازی و مقایسه می‌شوند و رزرو و اجرا در پلتفرم می‌ماند.

## چه چیزی ساخته شده (فاز MVP)

| بخش سند | پیاده‌سازی |
|---|---|
| §8 جریان End-to-End | ثبت RFQ ← ارزیابی ← Matching ← Dispatch ← ثبت Quote ← مقایسه ← Booking ← Milestone/POD |
| §10 AI Intake Agent | تبدیل متن آزاد (فارسی/انگلیسی) به پیش‌نویس RFQ با Claude؛ خروجی ساختاریافته و فقط «پیش‌نویس» |
| §11 مدل داده | Company، User، Provider، RFQ، Dispatch، Quote، Booking، AuditEvent |
| §12 استاندارد خدمت | درصد کامل بودن RFQ، بررسی اعتبار Quote پیش از رزرو، ثبت استثناها |
| §13 امتیاز Provider | وزن‌ها: ۲۵٪ زمان پاسخ، ۲۰٪ کامل بودن، ۲۰٪ قیمت، ۱۵٪ موفقیت رزرو، ۱۰٪ استثنا، ۱۰٪ انطباق |
| §15 ابزار | ماشین‌حساب CBM و وزن قابل‌محاسبه |
| §16 CRM | مراحل وضعیت RFQ و امتیاز لید |
| §17 Compliance | RFQهای مربوط به حوزه‌های قضایی حساس یا کالای کنترل‌شده متوقف می‌شوند تا مدیر تصمیم بگیرد؛ DG فقط به شرکت‌های دارای مجوز |
| §18 RACI | تعلیق Provider و تصمیم انطباق فقط با نقش admin؛ همه اقدامات در Audit log |
| §21 KPI | Quote Coverage، نرخ پاسخ، زمان تا اولین Quote، نرخ تبدیل، درآمد |

خارج از این نسخه (طبق سند): پرداخت/Escrow، اتصال WhatsApp و ایمیل، پورتال Provider، Tracking API، صفحات SEO.

## ساختار

```
backend/    FastAPI + SQLAlchemy (PostgreSQL در production، SQLite برای توسعه)
frontend/   Next.js فارسی و راست‌چین: صفحه اصلی، فرم RFQ، ماشین‌حساب، پیگیری، پنل عملیات (/ops)
docker-compose.yml + Caddyfile   اجرای کامل با HTTPS خودکار
```

## نصب روی سرور (Ubuntu + Docker)

۱. Docker را نصب کنید:
```bash
curl -fsSL https://get.docker.com | sh
```

۲. رکورد DNS دامنه (مثلاً `logirad.example.com`) را به IP سرور بدهید و پورت‌های 80 و 443 را باز کنید.

۳. کد را بگیرید و تنظیمات را بسازید:
```bash
git clone https://github.com/armaneiran50-crypto/armangiftub.git logirad && cd logirad
cp .env.example .env
nano .env   # DOMAIN، POSTGRES_PASSWORD، LOGIRAD_JWT_SECRET (openssl rand -hex 32)، LOGIRAD_ADMIN_PASSWORD
```

۴. اجرا:
```bash
docker compose up -d --build
```
سایت روی `https://DOMAIN` و پنل عملیات روی `https://DOMAIN/ops` در دسترس است
(ورود با `LOGIRAD_ADMIN_EMAIL` و `LOGIRAD_ADMIN_PASSWORD`). گواهی SSL را Caddy خودکار می‌گیرد.

به‌روزرسانی: `git pull && docker compose up -d --build`
پشتیبان دیتابیس: `docker compose exec db pg_dump -U logirad logirad > backup.sql`

### فعال‌سازی هوش مصنوعی (اختیاری)
در `.env` مقدار `LOGIRAD_AI_ENABLED=true` و `ANTHROPIC_API_KEY` را تنظیم کنید. دکمه «پر کردن خودکار با هوش مصنوعی»
متن مشتری را به فرم تبدیل می‌کند؛ هیچ RFQی بدون تأیید مشتری ثبت یا ارسال نمی‌شود.

## توسعه محلی

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000/docs
.venv/bin/python -m pytest                        # تست‌ها

# frontend (در ترمینال دیگر)
cd frontend && npm install && npm run dev         # http://localhost:3000
```
ورود پیش‌فرض در حالت توسعه: `admin@logirad.local` / `change-me`.
در حالت `LOGIRAD_ENV=production` برنامه با رمز یا JWT secret پیش‌فرض اجرا نمی‌شود.

## API اصلی

| متد | مسیر | دسترسی |
|---|---|---|
| POST | `/api/rfqs` | عمومی — ثبت درخواست |
| GET | `/api/rfqs/track/{reference}` | عمومی — پیگیری |
| POST | `/api/tools/chargeable-weight` | عمومی |
| POST | `/api/intake/parse` | عمومی — پیش‌نویس AI |
| GET/PATCH | `/api/rfqs`, `/api/rfqs/{id}` | ops/admin |
| GET | `/api/rfqs/{id}/matches` | ops/admin |
| POST | `/api/rfqs/{id}/dispatch` · `/quotes` · `/book` | ops/admin |
| GET | `/api/rfqs/{id}/compare` | ops/admin |
| POST | `/api/rfqs/{id}/compliance` | فقط admin |
| GET/POST/PATCH | `/api/providers` | ops/admin (تعلیق فقط admin) |
| POST | `/api/bookings/{id}/milestones` | ops/admin |
| GET | `/api/kpis`, `/api/audit` | ops/admin |

مستندات کامل تعاملی: `/docs` روی backend.
