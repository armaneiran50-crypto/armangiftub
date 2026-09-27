"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Login from "@/components/Login";
import { api } from "@/lib/api";
import { CARGO_CLASSES, countryName, fa, MODES, STATUSES } from "@/lib/labels";
import { useAuth } from "@/lib/useAuth";

type RFQ = {
  id: number; reference: string; status: string; origin_country: string | null; destination_country: string | null;
  mode: string | null; commodity: string | null; lead_score: number; completeness: number; flags: string[]; created_at: string;
  company_name: string | null;
};
type Provider = {
  id: number; legal_name: string; country: string; lanes: string[]; modes: string[]; cargo_classes: string[];
  tier: string; verified: boolean; suspended: boolean; score: number;
};
type Kpis = Record<string, number | null | Record<string, number>>;

const pct = (v: unknown) => (typeof v === "number" ? `${fa(v * 100)}٪` : "—");

export default function OpsPage() {
  const { me, ready, login, logout } = useAuth();
  const [tab, setTab] = useState<"rfqs" | "providers">("rfqs");
  const [status, setStatus] = useState("");
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [error, setError] = useState("");
  const router = useRouter();

  const load = useCallback(async () => {
    try {
      const [r, p, k] = await Promise.all([
        api<RFQ[]>(`/api/rfqs${status ? `?status=${status}` : ""}`, { auth: true }),
        api<Provider[]>("/api/providers", { auth: true }),
        api<Kpis>("/api/kpis", { auth: true }),
      ]);
      setRfqs(r); setProviders(p); setKpis(k); setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [status]);

  useEffect(() => { if (me) load(); }, [me, load]);

  if (!ready) return null;
  if (!me) return <main className="container"><Login onLogin={login} /></main>;

  return (
    <main className="container" style={{ paddingTop: 24 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>پنل عملیات</h1>
        <div className="row"><span className="muted ltr">{me.email}</span><button className="secondary" onClick={logout}>خروج</button></div>
      </div>

      {kpis && (
        <div className="kpis" style={{ marginTop: 20 }}>
          <div className="kpi"><small>کل درخواست‌ها</small><b>{fa(kpis.rfqs_total as number)}</b></div>
          <div className="kpi"><small>پوشش پیشنهاد قیمت</small><b>{pct(kpis.quote_coverage)}</b></div>
          <div className="kpi"><small>نرخ پاسخ شرکت‌ها</small><b>{pct(kpis.provider_response_rate)}</b></div>
          <div className="kpi"><small>میانگین زمان تا اولین قیمت</small><b>{kpis.avg_time_to_first_quote_hours == null ? "—" : `${fa(kpis.avg_time_to_first_quote_hours as number, 1)} ساعت`}</b></div>
          <div className="kpi"><small>نرخ تبدیل به رزرو</small><b>{pct(kpis.booking_conversion)}</b></div>
          <div className="kpi"><small>درآمد ناخالص (USD)</small><b>{fa(kpis.gross_revenue as number, 2)}</b></div>
        </div>
      )}
      {error && <div className="alert err">{error}</div>}

      <div className="tabs">
        <button className={tab === "rfqs" ? "active" : ""} onClick={() => setTab("rfqs")}>درخواست‌ها</button>
        <button className={tab === "providers" ? "active" : ""} onClick={() => setTab("providers")}>شرکت‌های حمل</button>
      </div>

      {tab === "rfqs" ? (
        <div className="card">
          <div className="row" style={{ marginBottom: 12 }}>
            <label style={{ margin: 0 }}>فیلتر وضعیت</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: "auto" }}>
              <option value="">همه</option>
              {Object.entries(STATUSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <button className="secondary" onClick={load}>بروزرسانی</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>کد</th><th>مسیر</th><th>حمل</th><th>کالا</th><th>امتیاز لید</th><th>وضعیت</th></tr></thead>
              <tbody>
                {rfqs.map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => router.push(`/ops/rfq/${r.id}`)}>
                    <td className="ltr">{r.reference}</td>
                    <td>{countryName(r.origin_country)} ← {countryName(r.destination_country)}</td>
                    <td>{r.mode ? MODES[r.mode] : "—"}</td>
                    <td>{r.commodity || "—"}{r.company_name ? <div className="muted">{r.company_name}</div> : null}</td>
                    <td className="num">{fa(r.lead_score)}</td>
                    <td>
                      <span className={`badge ${r.status === "compliance_hold" ? "warn" : r.status === "rejected" ? "err" : r.status === "booked" || r.status === "closed" ? "ok" : ""}`}>{STATUSES[r.status]}</span>
                      {r.flags.includes("dangerous_goods") && <span className="badge warn" style={{ marginInlineStart: 4 }}>DG</span>}
                    </td>
                  </tr>
                ))}
                {!rfqs.length && <tr><td colSpan={6} className="muted">درخواستی وجود ندارد.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <Providers providers={providers} onChange={load} isAdmin={me.role === "admin"} />
      )}
    </main>
  );
}

function Providers({ providers, onChange, isAdmin }: { providers: Provider[]; onChange: () => void; isAdmin: boolean }) {
  const [f, setF] = useState({ legal_name: "", country: "AE", contact_email: "", lanes: "CN->AE", modes: ["ocean_fcl"], dg: false, verified: false });
  const [error, setError] = useState("");

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/api/providers", {
        auth: true,
        body: {
          legal_name: f.legal_name, country: f.country, contact_email: f.contact_email || null,
          lanes: f.lanes.split(/[,\n،]/).map((s) => s.trim()).filter(Boolean),
          modes: f.modes, cargo_classes: f.dg ? ["general", "dg"] : ["general"], verified: f.verified,
        },
      });
      setF({ ...f, legal_name: "", contact_email: "" });
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function patch(id: number, body: object) {
    try {
      await api(`/api/providers/${id}`, { method: "PATCH", auth: true, body });
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>شرکت</th><th>مسیرها</th><th>حمل</th><th>امتیاز</th><th>سطح</th><th></th></tr></thead>
            <tbody>
              {providers.map((p) => (
                <tr key={p.id}>
                  <td>{p.legal_name} {p.verified && <span className="badge ok">تأیید شده</span>} {p.suspended && <span className="badge err">تعلیق</span>}</td>
                  <td className="ltr">{p.lanes.join(", ")}</td>
                  <td>{p.modes.map((m) => MODES[m]).join("، ")}{p.cargo_classes.includes("dg") && <> <span className="badge warn">DG</span></>}</td>
                  <td className="num">{fa(p.score, 1)}</td>
                  <td>
                    <select value={p.tier} style={{ width: "auto" }} onChange={(e) => patch(p.id, { tier: e.target.value })}>
                      <option value="preferred">ترجیحی</option><option value="standard">استاندارد</option><option value="probation">آزمایشی</option>
                    </select>
                  </td>
                  <td className="row">
                    {!p.verified && <button className="secondary" onClick={() => patch(p.id, { verified: true })}>تأیید</button>}
                    {isAdmin && <button className={p.suspended ? "secondary" : "danger"} onClick={() => patch(p.id, { suspended: !p.suspended })}>{p.suspended ? "رفع تعلیق" : "تعلیق"}</button>}
                  </td>
                </tr>
              ))}
              {!providers.length && <tr><td colSpan={6} className="muted">هنوز شرکتی ثبت نشده.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <form className="card" onSubmit={create}>
        <h2>افزودن شرکت حمل</h2>
        <div className="grid" style={{ marginTop: 12 }}>
          <div><label>نام حقوقی</label><input required value={f.legal_name} onChange={(e) => setF({ ...f, legal_name: e.target.value })} /></div>
          <div><label>کشور (کد دوحرفی)</label><input dir="ltr" required maxLength={2} value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })} /></div>
          <div><label>ایمیل</label><input dir="ltr" type="email" value={f.contact_email} onChange={(e) => setF({ ...f, contact_email: e.target.value })} /></div>
          <div><label>مسیرها (مثل {"CN->AE, TR->*"})</label><input dir="ltr" required value={f.lanes} onChange={(e) => setF({ ...f, lanes: e.target.value })} /></div>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          {Object.entries(MODES).map(([k, v]) => (
            <label key={k} className="row" style={{ margin: 0, color: "var(--text)" }}>
              <input type="checkbox" style={{ width: "auto" }} checked={f.modes.includes(k)}
                onChange={(e) => setF({ ...f, modes: e.target.checked ? [...f.modes, k] : f.modes.filter((m) => m !== k) })} /> {v}
            </label>
          ))}
          <label className="row" style={{ margin: 0, color: "var(--text)" }}><input type="checkbox" style={{ width: "auto" }} checked={f.dg} onChange={(e) => setF({ ...f, dg: e.target.checked })} /> {CARGO_CLASSES.dg}</label>
          <label className="row" style={{ margin: 0, color: "var(--text)" }}><input type="checkbox" style={{ width: "auto" }} checked={f.verified} onChange={(e) => setF({ ...f, verified: e.target.checked })} /> تأیید شده (KYB)</label>
        </div>
        {error && <div className="alert err">{error}</div>}
        <div className="actions"><button>افزودن</button></div>
      </form>
    </>
  );
}
