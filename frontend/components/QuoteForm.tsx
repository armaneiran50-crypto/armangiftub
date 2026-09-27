"use client";

import { useState } from "react";

type Line = { name: string; amount: string; category: string };
export type QuotePayload = {
  currency: string;
  charges: { name: string; amount: number; category: string | null }[];
  transit_days: number | null;
  valid_until: string | null;
  exclusions: string | null;
};

const firstLine = (): Line => ({ name: "Ocean freight", amount: "", category: "freight" });

/** Charge-line quote form shared by the Ops desk and the provider portal. */
export default function QuoteForm({ onSubmit, header, submitLabel = "ثبت پیشنهاد" }: {
  onSubmit: (q: QuotePayload) => Promise<boolean>;
  header?: React.ReactNode;
  submitLabel?: string;
}) {
  const [lines, setLines] = useState<Line[]>([firstLine()]);
  const [f, setF] = useState({ currency: "USD", transit_days: "", valid_until: "", exclusions: "" });
  const [busy, setBusy] = useState(false);
  const setLine = (i: number, k: keyof Line, v: string) => setLines(lines.map((x, j) => (j === i ? { ...x, [k]: v } : x)));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const ok = await onSubmit({
      currency: f.currency,
      charges: lines.filter((l) => l.amount !== "").map((l) => ({ name: l.name, amount: Number(l.amount), category: l.category || null })),
      transit_days: f.transit_days ? Number(f.transit_days) : null,
      valid_until: f.valid_until || null,
      exclusions: f.exclusions || null,
    });
    setBusy(false);
    if (ok) {
      setLines([firstLine()]);
      setF({ currency: "USD", transit_days: "", valid_until: "", exclusions: "" });
    }
  }

  const total = lines.reduce((s, l) => s + (Number(l.amount) || 0), 0);
  return (
    <form onSubmit={submit}>
      <div className="grid">
        {header}
        <div><label>ارز</label><input dir="ltr" maxLength={3} value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value.toUpperCase() })} /></div>
        <div><label>زمان ترانزیت (روز)</label><input type="number" min="1" dir="ltr" value={f.transit_days} onChange={(e) => setF({ ...f, transit_days: e.target.value })} /></div>
        <div><label>اعتبار تا</label><input type="date" dir="ltr" value={f.valid_until} onChange={(e) => setF({ ...f, valid_until: e.target.value })} /></div>
      </div>
      <h3>ردیف‌های هزینه</h3>
      {lines.map((l, i) => (
        <div className="grid" key={i} style={{ marginBottom: 8 }}>
          <input dir="ltr" placeholder="Charge name" value={l.name} onChange={(e) => setLine(i, "name", e.target.value)} />
          <input type="number" min="0" step="any" dir="ltr" placeholder="Amount" value={l.amount} onChange={(e) => setLine(i, "amount", e.target.value)} />
          <select value={l.category} onChange={(e) => setLine(i, "category", e.target.value)}>
            <option value="">تشخیص خودکار</option><option value="freight">کرایه اصلی</option><option value="origin">هزینه مبدأ</option>
            <option value="destination">هزینه مقصد</option><option value="other">سایر</option>
          </select>
        </div>
      ))}
      <div className="row">
        <button type="button" className="secondary" onClick={() => setLines([...lines, { name: "", amount: "", category: "" }])}>+ ردیف هزینه</button>
        {lines.length > 1 && <button type="button" className="secondary" onClick={() => setLines(lines.slice(0, -1))}>− ردیف</button>}
        <span className="muted num">جمع: {total.toLocaleString("fa-IR")} <span className="ltr">{f.currency}</span></span>
      </div>
      <div style={{ marginTop: 12 }}><label>استثناها (مثلاً عوارض گمرکی، بیمه)</label><input value={f.exclusions} onChange={(e) => setF({ ...f, exclusions: e.target.value })} /></div>
      <div className="actions"><button disabled={busy || !lines.some((l) => l.amount !== "")}>{submitLabel}</button></div>
    </form>
  );
}
