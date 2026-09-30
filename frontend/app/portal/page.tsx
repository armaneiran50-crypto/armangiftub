"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Login from "@/components/Login";
import { api } from "@/lib/api";
import { fa, MODES } from "@/lib/labels";
import { PORTAL_STATES, type PortalRFQ } from "@/lib/portal";
import { useAuth } from "@/lib/useAuth";

type Me = {
  company: string; tier: string; verified: boolean; lanes: string[]; score: number;
  stats: { rfqs_received: number; quotes_submitted: number; bookings_won: number; bookings_completed: number };
};

export default function PortalPage() {
  const { me, ready, login, logout } = useAuth();
  const [profile, setProfile] = useState<Me | null>(null);
  const [rows, setRows] = useState<PortalRFQ[]>([]);
  const [filter, setFilter] = useState<"open" | "all">("open");
  const [error, setError] = useState("");
  const router = useRouter();

  useEffect(() => {
    if (!me || me.role !== "provider") return;
    Promise.all([api<Me>("/api/portal/me", { auth: true }), api<PortalRFQ[]>("/api/portal/rfqs", { auth: true })])
      .then(([p, r]) => { setProfile(p); setRows(r); })
      .catch((e) => setError((e as Error).message));
  }, [me]);

  if (!ready) return null;
  if (!me) return <main className="container"><Login onLogin={login} title="ورود به پورتال شرکت‌های حمل" /></main>;
  if (me.role !== "provider")
    return <main className="container" style={{ paddingTop: 24 }}><div className="alert warn">این بخش برای شرکت‌های حمل است. <Link href="/ops">رفتن به پنل عملیات</Link></div></main>;

  const shown = filter === "open" ? rows.filter((r) => r.state === "pending") : rows;
  return (
    <main className="container" style={{ paddingTop: 24 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>پورتال {profile?.company || "شرکت حمل"}</h1>
        <div className="row"><Link href="/account">تغییر رمز</Link><button className="secondary" onClick={logout}>خروج</button></div>
      </div>
      {error && <div className="alert err">{error}</div>}
      {profile && (
        <div className="kpis" style={{ marginTop: 20 }}>
          <div className="kpi"><small>امتیاز عملکرد</small><b>{fa(profile.score, 1)}</b></div>
          <div className="kpi"><small>درخواست‌های دریافتی</small><b>{fa(profile.stats.rfqs_received)}</b></div>
          <div className="kpi"><small>قیمت‌های ارسالی</small><b>{fa(profile.stats.quotes_submitted)}</b></div>
          <div className="kpi"><small>رزروهای برنده</small><b>{fa(profile.stats.bookings_won)}</b></div>
        </div>
      )}
      <div className="alert warn" style={{ marginBottom: 16 }}>
        امتیاز شما بر اساس سرعت پاسخ، کامل بودن و رقابتی بودن قیمت‌ها و کیفیت اجرا محاسبه می‌شود و در اولویت دریافت درخواست‌ها اثر دارد.
      </div>
      <div className="tabs">
        <button className={filter === "open" ? "active" : ""} onClick={() => setFilter("open")}>منتظر قیمت ({fa(rows.filter((r) => r.state === "pending").length)})</button>
        <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>همه</button>
      </div>
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>کد</th><th>مسیر</th><th>حمل</th><th>کالا</th><th>بار</th><th>آمادگی</th><th>وضعیت</th></tr></thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.rfq_id} className="clickable" onClick={() => router.push(`/portal/rfq/${r.rfq_id}`)}>
                  <td className="ltr">{r.reference}</td>
                  <td className="ltr">{r.lane}<div className="muted">{[r.origin_city, r.destination_city].filter(Boolean).join(" → ")}</div></td>
                  <td>{r.mode ? MODES[r.mode] : "—"}</td>
                  <td>{r.commodity}{r.cargo_class === "dg" && <> <span className="badge warn">DG</span></>}</td>
                  <td className="num">{r.containers ? <span className="ltr">{r.containers}</span> : r.volume_cbm ? `${fa(r.volume_cbm, 2)} CBM` : ""} {r.weight_kg ? `/ ${fa(r.weight_kg)} kg` : ""}</td>
                  <td className="ltr">{r.ready_date || "—"}</td>
                  <td><span className={`badge ${PORTAL_STATES[r.state]?.[1] || ""}`}>{PORTAL_STATES[r.state]?.[0] || r.state}</span></td>
                </tr>
              ))}
              {!shown.length && <tr><td colSpan={7} className="muted">درخواستی برای نمایش نیست.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
