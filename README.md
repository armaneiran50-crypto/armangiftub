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
| §7 ضد دور زدن | پورتال شرکت‌های حمل (`/portal`): فقط درخواست‌های ارسال‌شده به همان شرکت، بدون نام و اطلاعات تماس صاحب کالا؛ ایمیل، تلفن و لینک در توضیحات خودکار مخفی می‌شوند |
| §13 عملیات شرکا | شرکت‌ها خودشان قیمت می‌دهند یا با ذکر دلیل انصراف می‌دهند؛ امتیاز و آمار خود را می‌بینند؛ حساب تعلیق‌شده وارد نمی‌شود |
| §14 واتس‌اپ | ربات فارسی/انگلیسی که از گفتگو RFQ می‌سازد (پیام آزاد یا پرسش‌وپاسخ، تاریخ شمسی، تأیید نهایی)؛ صندوق گفتگو در پنل عملیات با پاسخ دستی، توقف ربات و ارجاع به کارشناس؛ اطلاع به مشتری وقتی قیمت می‌رسد؛ دکمه واتس‌اپ در سایت |
| اطلاع‌رسانی | ایمیل به مشتری (ثبت درخواست)، به شرکت (درخواست جدید، برنده شدن) — از طریق SMTP |
| §21 KPI | Quote Coverage، نرخ پاسخ، زمان تا اولین Quote، نرخ تبدیل، درآمد |

خارج از این نسخه (طبق سند): پرداخت/Escrow، Tracking API.

### راه‌اندازی شرکت‌های حمل در پورتال
در پنل عملیات ← «شرکت‌های حمل» ← دکمه «دسترسی پورتال»، ایمیل شرکت را وارد کنید. یک رمز موقت نمایش داده می‌شود
که باید به شرکت بدهید؛ شرکت با آن در `/portal` وارد می‌شود و از صفحه «تغییر رمز» (`/account`) رمز را عوض می‌کند.

## ساختار

```
backend/    FastAPI + SQLAlchemy (PostgreSQL در production، SQLite برای توسعه)
frontend/   Next.js فارسی و راست‌چین: صفحه اصلی، فرم RFQ، ماشین‌حساب، پیگیری، پنل عملیات (/ops)، پورتال شرکت‌ها (/portal)
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

### واتس‌اپ (اختیاری)
۱. در [Meta for Developers](https://developers.facebook.com/) یک App از نوع Business بسازید و محصول WhatsApp را اضافه کنید.
۲. شماره کسب‌وکار را اضافه کنید و یک **System User token** دائمی با دسترسی `whatsapp_business_messaging` بسازید.
۳. در `.env` مقادیر `LOGIRAD_WHATSAPP_TOKEN`، `LOGIRAD_WHATSAPP_PHONE_NUMBER_ID`، `LOGIRAD_WHATSAPP_APP_SECRET` (از App Settings ← Basic)،
   یک رشته تصادفی برای `LOGIRAD_WHATSAPP_VERIFY_TOKEN` و شماره عمومی برای `LOGIRAD_WHATSAPP_DISPLAY_NUMBER` را وارد کنید و `docker compose up -d` بزنید.
۴. در تنظیمات Webhook واتس‌اپ، آدرس `https://DOMAIN/api/whatsapp/webhook` و همان Verify Token را وارد کنید و فیلد `messages` را Subscribe کنید.

گفتگوها در پنل عملیات ← «گفتگوهای واتس‌اپ» دیده می‌شوند. مشتری با نوشتن «کارشناس» به اپراتور وصل می‌شود؛
با «وضعیت» وضعیت آخرین درخواستش را می‌گیرد و با «جدید» از اول شروع می‌کند.
طبق قوانین واتس‌اپ، پاسخ آزاد فقط تا ۲۴ ساعت بعد از آخرین پیام مشتری ممکن است.

### ایمیل (اختیاری)
مقادیر `LOGIRAD_SMTP_*` را در `.env` وارد کنید (مثلاً SMTP سرویس ایمیل شرکت یا Amazon SES / Mailgun).
بدون SMTP، ایمیل‌ها فقط در لاگ backend ثبت می‌شوند.

### دیتابیس و migration
ساختار دیتابیس با Alembic مدیریت می‌شود و هنگام اجرای backend خودکار به آخرین نسخه ارتقا پیدا می‌کند؛
پس برای به‌روزرسانی فقط `git pull && docker compose up -d --build` کافی است.

### فعال‌سازی هوش مصنوعی (اختیاری)
در `.env` مقدار `LOGIRAD_AI_ENABLED=true` و `ANTHROPIC_API_KEY` را تنظیم کنید. دکمه «پر کردن خودکار با هوش مصنوعی»
متن مشتری را به فرم تبدیل می‌کند؛ هیچ RFQی بدون تأیید مشتری ثبت یا ارسال نمی‌شود.

## توسعه محلی

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000/docs
.venv/bin/python -m pytest                        # تست‌ها (SQLite)
LOGIRAD_TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/python -m pytest   # روی PostgreSQL
.venv/bin/alembic revision --autogenerate -m "..."  # بعد از تغییر مدل‌ها

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
| POST | `/api/providers/{id}/users` | ops/admin — ساخت دسترسی پورتال |
| GET | `/api/portal/me`, `/api/portal/rfqs`, `/api/portal/rfqs/{id}` | provider |
| POST | `/api/portal/rfqs/{id}/quote` · `/decline` | provider |
| POST | `/api/auth/password` | همه کاربران — تغییر رمز |
| GET/POST | `/api/whatsapp/webhook` | Meta (با امضای X-Hub-Signature-256) |
| GET/POST/PATCH | `/api/whatsapp/conversations…` | ops/admin — صندوق گفتگو |

مستندات کامل تعاملی: `/docs` روی backend.
