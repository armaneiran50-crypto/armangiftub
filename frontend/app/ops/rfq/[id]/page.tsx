"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Login from "@/components/Login";
import QuoteForm from "@/components/QuoteForm";
import { api } from "@/lib/api";
import { CARGO_CLASSES, countryName, fa, FIELDS, LABELS, MODES, STATUSES } from "@/lib/labels";
import { useAuth } from "@/lib/useAuth";

type RFQ = Record<string, unknown> & {
  id: number; reference: string; status: string; flags: string[]; missing_fields: string[];
  completeness: number; lead_score: number;
};
type Match = { provider_id: number; company: string; tier: string; verified: boolean; lane_fit: number; provider_score: number; match_score: number };
type Dispatch = { provider_id: number; company: string; responded_at: string | null; declined_at: string | null; decline_reason: string | null };
type CompareRow = {
  quote_id: number; provider_id: number; company: string; currency: string; total: number;
  by_category: Record<string, number>; transit_days: number | null; valid_until: string | null; expired: boolean;
  completeness: number; exclusions: string | null; labels: string[];
};
type Compare = { comparable: boolean; note: string | null; quotes: CompareRow[] };
type Booking = { id: number; rfq_id: number; status: string; platform_fee: number; milestones: { at: string; event: string; exception?: boolean }[] };

const FLAG_LABELS: Record<string, string> = {
  dangerous_goods: "کالای خطرناک — فقط شرکت‌های دارای مجوز DG",
  controlled_goods: "کالای احتمالاً کنترل‌شده — نیاز به بررسی صادراتی",
  compliance_released: "آزاد شده توسط مسئول انطباق",
};
const flagLabel = (f: string) =>
  f.startsWith("restricted_jurisdiction") ? `حوزه قضایی نیازمند بررسی (${f.split(":")[2]})` : FLAG_LABELS[f] || f;

export default function RFQDetail() {
  const { id } = useParams<{ id: string }>();
  const { me, ready, login } = useAuth();
  const [rfq, setRfq] = useState<RFQ | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [dispatches, setDispatches] = useState<Dispatch[]>([]);
  const [cmp, setCmp] = useState<Compare | null>(null);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, m, d, c, b] = await Promise.all([
        api<RFQ>(`/api/rfqs/${id}`, { auth: true }),
        api<Match[]>(`/api/rfqs/${id}/matches`, { auth: true }),
        api<Dispatch[]>(`/api/rfqs/${id}/dispatches`, { auth: true }),
        api<Compare>(`/api/rfqs/${id}/compare`, { auth: true }),
        api<Booking[]>(`/api/bookings`, { auth: true }),
      ]);
      setRfq(r); setMatches(m); setDispatches(d); setCmp(c);
      setBooking(b.find((x) => x.rfq_id === r.id) || null);
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    }
  }, [id]);

  useEffect(() => { if (me) load(); }, [me, load]);

  async function act(fn: () => Promise<unknown>, ok: string): Promise<boolean> {
    setMsg(null);
    try {
      await fn();
      setMsg({ kind: "ok", text: ok });
      await load();
      return true;
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
      return false;
    }
  }

  if (!ready) return null;
  if (!me) return <main className="container"><Login onLogin={login} /></main>;
  if (!rfq) return <main className="container" style={{ paddingTop: 24 }}>{msg ? <div className="alert err">{msg.text}</div> : "…"}</main>;

  const s = rfq.status;
  const canDispatch = ["qualified", "dispatched", "quoted"].includes(s);
  const dispatchedIds = new Set(dispatches.map((d) => d.provider_id));

  return (
    <main className="container" style={{ paddingTop: 24 }}>
      <Link href="/ops">→ بازگشت به فهرست</Link>
      <div className="row" style={{ justifyContent: "space-between", margin: "8px 0 16px" }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>درخواست <span className="ltr">{rfq.reference}</span></h1>
        <span className="badge brand">{STATUSES[s]}</span>
      </div>
      {msg && <div className={`alert ${msg.kind}`} style={{ marginBottom: 16 }}>{msg.text}</div>}

      <div className="cols">
        <div className="card">
          <h2>جزئیات</h2>
          <div className="result">
            <dl>
              <dt>مسیر</dt><dd>{countryName(rfq.origin_country as string)} {rfq.origin_city ? `(${rfq.origin_city})` : ""} ← {countryName(rfq.destination_country as string)} {rfq.destination_city ? `(${rfq.destination_city})` : ""}</dd>
              <dt>نوع حمل</dt><dd>{MODES[rfq.mode as string] || "—"}</dd>
              <dt>کالا</dt><dd>{(rfq.commodity as string) || "—"} — {CARGO_CLASSES[rfq.cargo_class as string] || ""}</dd>
              <dt>وزن / حجم</dt><dd className="num">{fa(rfq.weight_kg as number)} kg / {rfq.containers ? <span className="ltr">{rfq.containers as string}</span> : `${fa(rfq.volume_cbm as number, 2)} CBM`}</dd>
              <dt>اینکوترمز / آمادگی</dt><dd>{(rfq.incoterm as string) || "—"} / <span className="ltr">{(rfq.ready_date as string) || "—"}</span></dd>
              <dt>تماس</dt><dd>{(rfq.contact_name as string) || ""} {(rfq.company_name as string) || ""} <span className="ltr">{(rfq.contact_email as string) || ""} {(rfq.contact_phone as string) || ""}</span></dd>
              <dt>کامل بودن / امتیاز لید</dt><dd className="num">{fa(rfq.completeness * 100)}٪ / {fa(rfq.lead_score)}</dd>
            </dl>
            {rfq.notes ? <p className="muted">{rfq.notes as string}</p> : null}
          </div>
          {rfq.missing_fields.length > 0 && <div className="alert warn">موارد ناقص: {rfq.missing_fields.map((m) => FIELDS[m] || m).join("، ")}</div>}
          {rfq.flags.map((f) => <div key={f} className="alert warn">{flagLabel(f)}</div>)}
        </div>

        <div>
          {s === "compliance_hold" && <Compliance isAdmin={me.role === "admin"} onDecide={(decision, reason) =>
            act(() => api(`/api/rfqs/${id}/compliance`, { auth: true, body: { decision, reason } }), "تصمیم ثبت شد.")} />}
          {booking && <BookingCard booking={booking} onMilestone={(body) =>
            act(() => api(`/api/bookings/${booking.id}/milestones`, { auth: true, body }), "رویداد ثبت شد.")} />}
        </div>
      </div>

      {canDispatch && (
        <div className="card">
          <h2>شرکت‌های منطبق</h2>
          <p className="sub">رتبه‌بندی بر اساس مسیر، نوع حمل، امتیاز عملکرد و سطح شرکت.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>شرکت</th><th>تطابق مسیر</th><th>امتیاز عملکرد</th><th>امتیاز تطابق</th><th>وضعیت</th></tr></thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.provider_id}>
                    <td>{m.company} {m.verified && <span className="badge ok">تأیید شده</span>}</td>
                    <td>{m.lane_fit === 1 ? "دقیق" : "عمومی"}</td>
                    <td className="num">{fa(m.provider_score, 1)}</td>
                    <td className="num">{fa(m.match_score, 1)}</td>
                    <td><DispatchState d={dispatches.find((d) => d.provider_id === m.provider_id)} /></td>
                  </tr>
                ))}
                {!matches.length && <tr><td colSpan={5} className="muted">هیچ شرکت واجد شرایطی برای این مسیر و نوع حمل نیست.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button disabled={!matches.some((m) => !dispatchedIds.has(m.provider_id))}
              onClick={() => act(() => api(`/api/rfqs/${id}/dispatch`, { auth: true, method: "POST" }), "درخواست برای شرکت‌های برتر ارسال شد.")}>
              ارسال به شرکت‌های برتر
            </button>
          </div>
        </div>
      )}

      {["dispatched", "quoted"].includes(s) && dispatches.length > 0 && (
        <QuoteEntry dispatches={dispatches} onSubmit={(body) => act(() => api(`/api/rfqs/${id}/quotes`, { auth: true, body }), "پیشنهاد قیمت ثبت شد.")} />
      )}

      {cmp && cmp.quotes.length > 0 && (
        <div className="card">
          <h2>مقایسه پیشنهادها</h2>
          {cmp.note && <div className="alert warn">ارزهای پیشنهادها متفاوت است؛ پیش از مقایسه مجموع‌ها، تبدیل ارز انجام دهید.</div>}
          <div className="table-wrap">
            <table>
              <thead><tr><th>شرکت</th><th>کرایه اصلی</th><th>مبدأ</th><th>مقصد</th><th>سایر</th><th>جمع</th><th>ترانزیت</th><th>اعتبار تا</th><th></th></tr></thead>
              <tbody>
                {cmp.quotes.map((q) => (
                  <tr key={q.quote_id}>
                    <td>{q.company}<div>{q.labels.map((l) => <span key={l} className="badge ok" style={{ marginInlineEnd: 4 }}>{LABELS[l]}</span>)}</div>
                      {q.exclusions && <div className="muted">استثنا: {q.exclusions}</div>}</td>
                    {(["freight", "origin", "destination", "other"] as const).map((c) => <td key={c} className="num">{fa(q.by_category[c], 2)}</td>)}
                    <td className="num"><b>{fa(q.total, 2)}</b> <span className="ltr">{q.currency}</span></td>
                    <td className="num">{q.transit_days ? `${fa(q.transit_days)} روز` : "—"}</td>
                    <td className="ltr">{q.valid_until || "—"} {q.expired && <span className="badge err">منقضی</span>}</td>
                    <td className="row">
                      {s === "quoted" && !q.expired && (
                        <button onClick={() => {
                          const fee = prompt("کارمزد پلتفرم (USD)", "0");
                          if (fee !== null) act(() => api(`/api/rfqs/${id}/book`, { auth: true, body: { quote_id: q.quote_id, platform_fee: Number(fee) || 0 } }), "رزرو انجام شد.");
                        }}>رزرو</button>
                      )}
                      {s === "quoted" && (
                        <button className="secondary" onClick={() => act(() => api(`/api/rfqs/${id}/quotes/${q.quote_id}/reject`, { auth: true, method: "POST" }), "پیشنهاد رد شد.")}>رد</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}

function DispatchState({ d }: { d?: Dispatch }) {
  if (!d) return <>—</>;
  if (d.responded_at) return <span className="badge ok">قیمت داده</span>;
  if (d.declined_at) return <span className="badge err" title={d.decline_reason || ""}>انصراف: {d.decline_reason}</span>;
  return <span className="badge brand">منتظر پاسخ</span>;
}

function Compliance({ isAdmin, onDecide }: { isAdmin: boolean; onDecide: (d: "release" | "reject", reason: string) => void }) {
  const [reason, setReason] = useState("");
  return (
    <div className="card">
      <h2>بررسی انطباق</h2>
      <p className="sub">این درخواست تا تصمیم مسئول انطباق برای هیچ شرکتی ارسال نمی‌شود.</p>
      {isAdmin ? (
        <>
          <label>دلیل تصمیم (ثبت در لاگ)</label>
          <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="actions">
            <button disabled={reason.trim().length < 5} onClick={() => onDecide("release", reason)}>آزادسازی</button>
            <button className="danger" disabled={reason.trim().length < 5} onClick={() => onDecide("reject", reason)}>رد درخواست</button>
          </div>
        </>
      ) : <div className="alert warn">فقط مدیر مجاز به تصمیم‌گیری است.</div>}
    </div>
  );
}

function QuoteEntry({ dispatches, onSubmit }: { dispatches: Dispatch[]; onSubmit: (body: object) => Promise<boolean> }) {
  const open = dispatches.filter((d) => !d.declined_at);
  const [provider, setProvider] = useState<number>((open.find((d) => !d.responded_at) || open[0] || dispatches[0]).provider_id);
  return (
    <div className="card">
      <h2>ثبت پیشنهاد قیمت دریافتی</h2>
      <p className="sub">پیشنهادهایی که از ایمیل یا واتس‌اپ می‌رسند را اینجا وارد کنید؛ شرکت‌ها می‌توانند خودشان هم از پورتال قیمت بدهند.</p>
      <QuoteForm onSubmit={(q) => onSubmit({ ...q, provider_id: provider })} header={
        <div><label>شرکت</label>
          <select value={provider} onChange={(e) => setProvider(Number(e.target.value))}>
            {dispatches.map((d) => <option key={d.provider_id} value={d.provider_id}>
              {d.company}{d.responded_at ? " (قیمت داده)" : d.declined_at ? " (انصراف)" : ""}</option>)}
          </select></div>
      } />
    </div>
  );
}

function BookingCard({ booking, onMilestone }: { booking: Booking; onMilestone: (body: object) => void }) {
  const [event, setEvent] = useState("");
  const [status, setStatus] = useState("");
  const [exception, setException] = useState(false);
  const open = !["delivered", "cancelled"].includes(booking.status);
  const BS: Record<string, string> = { confirmed: "تأیید شده", in_transit: "در مسیر", delivered: "تحویل شده", cancelled: "لغو شده" };
  return (
    <div className="card">
      <h2>رزرو <span className="badge brand">{BS[booking.status]}</span></h2>
      <p className="sub">کارمزد پلتفرم: {fa(booking.platform_fee, 2)} USD</p>
      <ul style={{ paddingInlineStart: 18, margin: 0 }}>
        {booking.milestones.map((m, i) => (
          <li key={i}><span className="muted ltr">{new Date(m.at).toLocaleString("fa-IR")}</span> — {m.event} {m.exception && <span className="badge err">استثنا</span>}</li>
        ))}
      </ul>
      {open && (
        <>
          <div className="grid" style={{ marginTop: 12 }}>
            <input placeholder="رویداد (مثلاً کشتی حرکت کرد)" value={event} onChange={(e) => setEvent(e.target.value)} />
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">بدون تغییر وضعیت</option><option value="in_transit">در مسیر</option><option value="delivered">تحویل شد (POD)</option><option value="cancelled">لغو</option>
            </select>
          </div>
          <label className="row" style={{ marginTop: 8, color: "var(--text)" }}><input type="checkbox" style={{ width: "auto" }} checked={exception} onChange={(e) => setException(e.target.checked)} /> این رویداد یک استثنا/مشکل است</label>
          <div className="actions"><button disabled={!event.trim()} onClick={() => { onMilestone({ event, status: status || null, exception }); setEvent(""); setStatus(""); setException(false); }}>ثبت رویداد</button></div>
        </>
      )}
    </div>
  );
}
