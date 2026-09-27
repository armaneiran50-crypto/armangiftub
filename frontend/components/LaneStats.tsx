"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fa, MODES } from "@/lib/labels";

type Stats = { providers: number; modes: Record<string, { providers: number; verified_providers: number; quotes?: number; median_transit_days?: number }> };

/** Live network data for a lane: active providers and median quoted transit (when enough quotes exist). */
export default function LaneStats({ origin, destination }: { origin: string; destination: string }) {
  const [s, setS] = useState<Stats | null>(null);
  useEffect(() => { api<Stats>(`/api/lanes/${origin}/${destination}`).then(setS).catch(() => {}); }, [origin, destination]);
  if (!s || s.providers === 0) return null;
  return (
    <div className="card">
      <h2>شبکه لجی‌راد در این مسیر</h2>
      <p className="sub">داده زنده از شرکت‌های فعال و پیشنهادهای ثبت‌شده در پلتفرم.</p>
      <div className="kpis" style={{ marginBottom: 0 }}>
        <div className="kpi"><small>شرکت‌های حمل فعال</small><b>{fa(s.providers)}</b></div>
        {Object.entries(s.modes).map(([m, v]) => (
          <div className="kpi" key={m}>
            <small>{MODES[m]}</small>
            <b>{fa(v.providers)} <span style={{ fontSize: 14, fontWeight: 400 }}>شرکت</span></b>
            {v.median_transit_days != null && <small>میانه ترانزیت پیشنهادی: {fa(v.median_transit_days)} روز</small>}
          </div>
        ))}
      </div>
    </div>
  );
}
