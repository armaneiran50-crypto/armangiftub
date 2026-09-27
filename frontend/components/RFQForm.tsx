"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAiEnabled } from "@/lib/useConfig";
import { CARGO_CLASSES, COUNTRIES, FIELDS, MODES, STATUSES } from "@/lib/labels";

type Form = Record<string, string>;

const EMPTY: Form = {
  contact_name: "", contact_email: "", contact_phone: "", company_name: "",
  origin_country: "CN", origin_city: "", destination_country: "AE", destination_city: "",
  mode: "ocean_fcl", commodity: "", cargo_class: "general", weight_kg: "", volume_cbm: "",
  containers: "", incoterm: "", ready_date: "", notes: "",
};

const NUMERIC = ["weight_kg", "volume_cbm"];

function payload(f: Form) {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(f)) {
    if (v === "") continue;
    out[k] = NUMERIC.includes(k) ? Number(v) : v;
  }
  return out;
}

type Result = { reference: string; status: string; missing_fields: string[] };

export default function RFQForm({ initial }: { initial?: Partial<Form> } = {}) {
  const start: Form = { ...EMPTY, ...(initial as Form | undefined) };
  const [f, setF] = useState<Form>(start);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [aiText, setAiText] = useState("");
  const aiEnabled = useAiEnabled();
  const [aiMsg, setAiMsg] = useState<{ kind: "ok" | "warn" | "err"; text: string } | null>(null);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api<Result>("/api/rfqs", { body: payload(f) }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function aiFill() {
    setBusy(true);
    setAiMsg(null);
    try {
      const r = await api<{ draft: Record<string, unknown>; questions: string[] }>("/api/intake/parse", { body: { text: aiText } });
      const next = { ...f };
      for (const [k, v] of Object.entries(r.draft)) if (k in next && v != null) next[k] = String(v);
      setF(next);
      setAiMsg({
        kind: r.questions.length ? "warn" : "ok",
        text: r.questions.length ? "فرم پر شد. لطفاً این موارد را تکمیل کنید: " + r.questions.join(" • ") : "فرم پر شد؛ لطفاً بررسی و ارسال کنید.",
      });
    } catch (err) {
      setAiMsg({ kind: "err", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="card" id="rfq">
        <h2>درخواست شما ثبت شد</h2>
        <p>
          کد پیگیری: <b className="ltr">{result.reference}</b> — وضعیت: <span className="badge brand">{STATUSES[result.status]}</span>
        </p>
        {result.status === "compliance_hold" && (
          <div className="alert warn">این درخواست پیش از ارسال به شرکت‌های حمل، توسط تیم انطباق بررسی می‌شود.</div>
        )}
        {result.missing_fields.length > 0 && (
          <div className="alert warn">
            برای دریافت قیمت، تیم ما برای تکمیل این موارد با شما تماس می‌گیرد: {result.missing_fields.map((m) => FIELDS[m] || m).join("، ")}
          </div>
        )}
        <div className="actions">
          <button className="secondary" onClick={() => { setResult(null); setF(start); }}>ثبت درخواست جدید</button>
        </div>
      </div>
    );
  }

  const isFcl = f.mode === "ocean_fcl";
  return (
    <form className="card" id="rfq" onSubmit={submit}>
      <h2>درخواست قیمت حمل</h2>
      <p className="sub">ثبت درخواست رایگان است. پیشنهادهای قابل مقایسه از شرکت‌های حمل معتبر دریافت می‌کنید.</p>

      {aiEnabled && <div className="result">
        <label htmlFor="ai">یا درخواستتان را آزاد بنویسید تا فرم خودکار پر شود (فارسی یا انگلیسی)</label>
        <textarea id="ai" rows={3} value={aiText} onChange={(e) => setAiText(e.target.value)}
          placeholder="مثلاً: دو کانتینر ۴۰ فوت مبلمان از شانگهای به جبل علی، حدود ۲۰ تن، آماده حمل اول آذر" />
        <div className="actions">
          <button type="button" className="secondary" disabled={busy || aiText.trim().length < 10} onClick={aiFill}>پر کردن خودکار با هوش مصنوعی</button>
        </div>
        {aiMsg && <div className={`alert ${aiMsg.kind}`}>{aiMsg.text}</div>}
      </div>}

      <h3>مسیر و بار</h3>
      <div className="grid">
        <div>
          <label>کشور مبدأ</label>
          <select value={f.origin_country} onChange={set("origin_country")}>
            {COUNTRIES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </div>
        <div><label>شهر / بندر مبدأ</label><input value={f.origin_city} onChange={set("origin_city")} /></div>
        <div>
          <label>کشور مقصد</label>
          <select value={f.destination_country} onChange={set("destination_country")}>
            {COUNTRIES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </div>
        <div><label>شهر / بندر مقصد</label><input value={f.destination_city} onChange={set("destination_city")} /></div>
        <div>
          <label>نوع حمل</label>
          <select value={f.mode} onChange={set("mode")}>
            {Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div><label>نوع کالا *</label><input required value={f.commodity} onChange={set("commodity")} /></div>
        <div>
          <label>دسته بار</label>
          <select value={f.cargo_class} onChange={set("cargo_class")}>
            {Object.entries(CARGO_CLASSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div><label>وزن کل (کیلوگرم) *</label><input required type="number" min="1" dir="ltr" value={f.weight_kg} onChange={set("weight_kg")} /></div>
        {isFcl ? (
          <div>
            <label>کانتینر (مثلاً 2x40HC)</label>
            <input dir="ltr" pattern="^\d+x(20GP|40GP|40HC|45HC|20RF|40RF)(,\d+x(20GP|40GP|40HC|45HC|20RF|40RF))*$"
              placeholder="1x40HC" value={f.containers} onChange={set("containers")} />
          </div>
        ) : (
          <div><label>حجم (CBM)</label><input type="number" step="0.01" min="0.01" dir="ltr" value={f.volume_cbm} onChange={set("volume_cbm")} /></div>
        )}
        <div>
          <label>اینکوترمز</label>
          <select value={f.incoterm} onChange={set("incoterm")}>
            <option value="">نمی‌دانم</option>
            {["EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"].map((i) => <option key={i}>{i}</option>)}
          </select>
        </div>
        <div><label>تاریخ آمادگی بار *</label><input required type="date" dir="ltr" value={f.ready_date} onChange={set("ready_date")} /></div>
      </div>
      <div style={{ marginTop: 12 }}>
        <label>توضیحات</label>
        <textarea rows={2} value={f.notes} onChange={set("notes")} />
      </div>

      <h3>اطلاعات تماس</h3>
      <div className="grid">
        <div><label>نام</label><input value={f.contact_name} onChange={set("contact_name")} /></div>
        <div><label>شرکت</label><input value={f.company_name} onChange={set("company_name")} /></div>
        <div><label>ایمیل</label><input type="email" dir="ltr" value={f.contact_email} onChange={set("contact_email")} /></div>
        <div><label>تلفن / واتس‌اپ</label><input dir="ltr" value={f.contact_phone} onChange={set("contact_phone")} /></div>
      </div>

      <p className="muted" style={{ fontSize: 13 }}>حداقل یکی از ایمیل یا شماره تماس را وارد کنید.</p>
      {error && <div className="alert err">{error}</div>}
      <div className="actions"><button disabled={busy || (!f.contact_email && !f.contact_phone)}>{busy ? "در حال ارسال…" : "دریافت پیشنهاد قیمت"}</button></div>
    </form>
  );
}
