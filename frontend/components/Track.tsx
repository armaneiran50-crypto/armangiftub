"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { FIELDS, STATUSES } from "@/lib/labels";

export default function Track() {
  const [ref, setRef] = useState("");
  const [res, setRes] = useState<{ reference: string; status: string; missing_fields: string[] } | null>(null);
  const [error, setError] = useState("");

  async function go(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setRes(null);
    try {
      setRes(await api(`/api/rfqs/track/${encodeURIComponent(ref.trim())}`));
    } catch (err) {
      setError((err as Error).message === "RFQ not found" ? "درخواستی با این کد پیدا نشد." : (err as Error).message);
    }
  }

  return (
    <form className="card" id="track" onSubmit={go}>
      <h2>پیگیری درخواست</h2>
      <div className="row">
        <input dir="ltr" placeholder="LR-XXXXXXXXXX" value={ref} onChange={(e) => setRef(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
        <button disabled={!ref.trim()}>پیگیری</button>
      </div>
      {error && <div className="alert err">{error}</div>}
      {res && (
        <div className="result">
          وضعیت <b className="ltr">{res.reference}</b>: <span className="badge brand">{STATUSES[res.status]}</span>
          {res.missing_fields.length > 0 && <div className="muted">موارد ناقص: {res.missing_fields.map((m) => FIELDS[m] || m).join("، ")}</div>}
        </div>
      )}
    </form>
  );
}
