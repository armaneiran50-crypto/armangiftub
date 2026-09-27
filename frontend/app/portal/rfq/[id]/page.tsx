"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Login from "@/components/Login";
import QuoteForm from "@/components/QuoteForm";
import { api } from "@/lib/api";
import { CARGO_CLASSES, fa, MODES } from "@/lib/labels";
import { useAuth } from "@/lib/useAuth";
import { PORTAL_STATES, type PortalRFQ } from "@/lib/portal";

type Detail = PortalRFQ & {
  hs_code: string | null; notes: string | null; decline_reason: string | null;
  quote: { currency: string; total: number; charges: { category: string; name: string; amount: number }[]; transit_days: number | null; valid_until: string | null; exclusions: string | null; status: string } | null;
};
const CAT: Record<string, string> = { freight: "کرایه اصلی", origin: "مبدأ", destination: "مقصد", other: "سایر" };

export default function PortalRFQ() {
  const { id } = useParams<{ id: string }>();
  const { me, ready, login } = useAuth();
  const [d, setD] = useState<Detail | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(() => api<Detail>(`/api/portal/rfqs/${id}`, { auth: true }).then(setD)
    .catch((e) => setMsg({ kind: "err", text: (e as Error).message })), [id]);
  useEffect(() => { if (me) load(); }, [me, load]);

  async function act(fn: () => Promise<unknown>, ok: string) {
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
  if (!me) return <main className="container"><Login onLogin={login} title="ورود به پورتال شرکت‌های حمل" /></main>;
  if (!d) return <main className="container" style={{ paddingTop: 24 }}>{msg ? <div className="alert err">{msg.text}</div> : "…"}</main>;

  const [stateLabel, stateKind] = PORTAL_STATES[d.state] || [d.state, ""];
  return (
    <main className="container" style={{ paddingTop: 24 }}>
      <Link href="/portal">→ بازگشت به فهرست</Link>
      <div className="row" style={{ justifyContent: "space-between", margin: "8px 0 16px" }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>درخواست <span className="ltr">{d.reference}</span></h1>
        <span className={`badge ${stateKind}`}>{stateLabel}</span>
      </div>
      {msg && <div className={`alert ${msg.kind}`} style={{ marginBottom: 16 }}>{msg.text}</div>}

      <div className="cols">
        <div className="card">
          <h2>مشخصات بار</h2>
          <div className="result">
            <dl>
              <dt>مسیر</dt><dd className="ltr">{d.lane} {[d.origin_city, d.destination_city].filter(Boolean).join(" → ")}</dd>
              <dt>نوع حمل</dt><dd>{d.mode ? MODES[d.mode] : "—"}</dd>
              <dt>کالا</dt><dd>{d.commodity} — {CARGO_CLASSES[d.cargo_class || "general"]} {d.hs_code && <span className="ltr">(HS {d.hs_code})</span>}</dd>
              <dt>وزن</dt><dd className="num">{fa(d.weight_kg)} kg</dd>
              <dt>کانتینر / حجم</dt><dd>{d.containers ? <span className="ltr">{d.containers}</span> : d.volume_cbm ? `${fa(d.volume_cbm, 2)} CBM` : "—"}</dd>
              <dt>اینکوترمز</dt><dd>{d.incoterm || "—"}</dd>
              <dt>آمادگی بار</dt><dd className="ltr">{d.ready_date || "—"}</dd>
            </dl>
            {d.notes && <p className="muted">{d.notes}</p>}
          </div>
          <p className="muted" style={{ fontSize: 13 }}>اطلاعات تماس صاحب کالا تا زمان رزرو از طریق پلتفرم مدیریت می‌شود.</p>
        </div>

        <div>
          {d.quote && (
            <div className="card">
              <h2>قیمت شما</h2>
              <table>
                <tbody>
                  {d.quote.charges.map((c, i) => <tr key={i}><td>{CAT[c.category]}</td><td className="ltr">{c.name}</td><td className="num">{fa(c.amount, 2)}</td></tr>)}
                  <tr><td colSpan={2}><b>جمع</b></td><td className="num"><b>{fa(d.quote.total, 2)} <span className="ltr">{d.quote.currency}</span></b></td></tr>
                </tbody>
              </table>
              <p className="muted">ترانزیت: {d.quote.transit_days ? `${fa(d.quote.transit_days)} روز` : "—"} — اعتبار تا: <span className="ltr">{d.quote.valid_until || "—"}</span></p>
            </div>
          )}
          {d.state === "declined" && <div className="card"><h2>انصراف</h2><p>دلیل: {d.decline_reason}</p></div>}
        </div>
      </div>

      {d.state === "pending" && (
        <>
          <div className="card">
            <h2>ارسال قیمت</h2>
            <p className="sub">هزینه‌ها را به تفکیک وارد کنید؛ قیمت‌های کامل‌تر و سریع‌تر امتیاز بیشتری می‌گیرند.</p>
            <QuoteForm submitLabel="ارسال قیمت" onSubmit={(q) => act(() => api(`/api/portal/rfqs/${id}/quote`, { auth: true, body: q }), "قیمت شما ارسال شد.")} />
          </div>
          <div className="card">
            <h2>انصراف از این درخواست</h2>
            <div className="row">
              <select value={reason} onChange={(e) => setReason(e.target.value)} style={{ flex: 1, minWidth: 200 }}>
                <option value="">دلیل را انتخاب کنید</option>
                <option>No capacity / ظرفیت نداریم</option>
                <option>Lane not served / این مسیر را پوشش نمی‌دهیم</option>
                <option>Cargo not accepted / این نوع بار را نمی‌پذیریم</option>
                <option>Insufficient information / اطلاعات کافی نیست</option>
              </select>
              <button className="secondary" disabled={!reason} onClick={() => act(() => api(`/api/portal/rfqs/${id}/decline`, { auth: true, body: { reason } }), "انصراف ثبت شد.")}>ثبت انصراف</button>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
