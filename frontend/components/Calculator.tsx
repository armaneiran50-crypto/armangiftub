"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { fa, MODES } from "@/lib/labels";

type Item = { length_cm: string; width_cm: string; height_cm: string; weight_kg: string; quantity: string };
type Res = { total_cbm: number; gross_weight_kg: number; volumetric_weight_kg: number; chargeable_weight_kg: number; basis: string; revenue_tons?: number };

const blank: Item = { length_cm: "", width_cm: "", height_cm: "", weight_kg: "", quantity: "1" };

export default function Calculator() {
  const [mode, setMode] = useState("air");
  const [items, setItems] = useState<Item[]>([{ ...blank }]);
  const [res, setRes] = useState<Res | null>(null);
  const [error, setError] = useState("");

  const upd = (i: number, k: keyof Item, v: string) => setItems(items.map((it, j) => (j === i ? { ...it, [k]: v } : it)));

  async function calc(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      setRes(await api<Res>("/api/tools/chargeable-weight", {
        body: { mode, items: items.map((it) => Object.fromEntries(Object.entries(it).map(([k, v]) => [k, Number(v)]))) },
      }));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card" id="calculator" onSubmit={calc}>
      <h2>ماشین‌حساب CBM و وزن قابل‌محاسبه</h2>
      <p className="sub">ابعاد بسته‌ها را وارد کنید تا حجم و وزن مبنای کرایه را ببینید.</p>
      <label>نوع حمل</label>
      <select value={mode} onChange={(e) => setMode(e.target.value)}>
        {Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      {items.map((it, i) => (
        <div className="grid" key={i} style={{ marginTop: 10, gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}>
          {(["length_cm", "width_cm", "height_cm", "weight_kg", "quantity"] as const).map((k) => (
            <div key={k}>
              {i === 0 && <label>{{ length_cm: "طول cm", width_cm: "عرض cm", height_cm: "ارتفاع cm", weight_kg: "وزن kg", quantity: "تعداد" }[k]}</label>}
              <input required type="number" min="0.01" step="any" dir="ltr" value={it[k]} onChange={(e) => upd(i, k, e.target.value)} />
            </div>
          ))}
        </div>
      ))}
      <div className="actions">
        <button type="button" className="secondary" onClick={() => setItems([...items, { ...blank }])}>+ ردیف</button>
        {items.length > 1 && <button type="button" className="secondary" onClick={() => setItems(items.slice(0, -1))}>− ردیف</button>}
        <button>محاسبه</button>
      </div>
      {error && <div className="alert err">{error}</div>}
      {res && (
        <div className="result">
          <dl>
            <dt>حجم کل</dt><dd className="num">{fa(res.total_cbm, 3)} CBM</dd>
            <dt>وزن ناخالص</dt><dd className="num">{fa(res.gross_weight_kg, 2)} kg</dd>
            <dt>وزن حجمی</dt><dd className="num">{fa(res.volumetric_weight_kg, 2)} kg</dd>
            <dt>وزن قابل‌محاسبه</dt><dd className="num">{fa(res.chargeable_weight_kg, 2)} kg ({res.basis === "volume" ? "بر اساس حجم" : "بر اساس وزن"})</dd>
            {res.revenue_tons != null && (<><dt>Revenue Ton</dt><dd className="num">{fa(res.revenue_tons, 3)}</dd></>)}
          </dl>
        </div>
      )}
    </form>
  );
}
