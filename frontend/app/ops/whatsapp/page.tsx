"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Login from "@/components/Login";
import { api } from "@/lib/api";
import { STATUSES } from "@/lib/labels";
import { useAuth } from "@/lib/useAuth";

type Conv = {
  id: number; wa_id: string; name: string | null; state: string; needs_human: boolean; updated_at: string;
  window_open: boolean; draft: Record<string, unknown>; rfq_id: number | null;
  last_message: { direction: string; body: string } | null;
};
type Msg = { id: number; direction: string; body: string; sender: string; delivery: string; at: string };
type Detail = Conv & { messages: Msg[]; rfq?: { id: number; reference: string; status: string } };

const STATE: Record<string, string> = { idle: "آماده", collecting: "در حال دریافت اطلاعات", confirming: "منتظر تأیید", handoff: "در دست کارشناس" };

export default function WhatsAppInbox() {
  const { me, ready, login } = useAuth();
  const [convs, setConvs] = useState<Conv[]>([]);
  const [onlyHuman, setOnlyHuman] = useState(false);
  const [sel, setSel] = useState<Detail | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  const loadList = useCallback(() => api<Conv[]>(`/api/whatsapp/conversations${onlyHuman ? "?needs_human=true" : ""}`, { auth: true })
    .then(setConvs).catch((e) => setError((e as Error).message)), [onlyHuman]);
  const open = useCallback((id: number) => api<Detail>(`/api/whatsapp/conversations/${id}`, { auth: true })
    .then((d) => { setSel(d); setTimeout(() => bottom.current?.scrollIntoView(), 50); })
    .catch((e) => setError((e as Error).message)), []);

  useEffect(() => {
    if (!me) return;
    loadList();
    const t = setInterval(() => { loadList(); if (sel) open(sel.id); }, 10000);
    return () => clearInterval(t);
  }, [me, loadList, open, sel]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!sel) return;
    try {
      await api(`/api/whatsapp/conversations/${sel.id}/reply`, { auth: true, body: { text } });
      setText("");
      setError("");
      await open(sel.id);
      loadList();
    } catch (err) {
      setError((err as Error).message.startsWith("The 24-hour") ? "۲۴ ساعت از آخرین پیام مشتری گذشته؛ واتس‌اپ اجازه پیام آزاد نمی‌دهد تا مشتری دوباره پیام بدهد." : (err as Error).message);
    }
  }

  async function patch(body: object) {
    if (!sel) return;
    await api(`/api/whatsapp/conversations/${sel.id}`, { method: "PATCH", auth: true, body });
    await open(sel.id);
    loadList();
  }

  if (!ready) return null;
  if (!me) return <main className="container"><Login onLogin={login} /></main>;

  return (
    <main className="container" style={{ paddingTop: 24 }}>
      <Link href="/ops">→ پنل عملیات</Link>
      <h1 style={{ margin: "8px 0 16px", fontSize: 24 }}>گفتگوهای واتس‌اپ</h1>
      {error && <div className="alert err" style={{ marginBottom: 12 }}>{error}</div>}
      <div className="wa-grid">
        <div className="card" style={{ padding: 0 }}>
          <div className="row" style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
            <label className="row" style={{ margin: 0, color: "var(--text)" }}>
              <input type="checkbox" style={{ width: "auto" }} checked={onlyHuman} onChange={(e) => setOnlyHuman(e.target.checked)} /> فقط نیازمند کارشناس
            </label>
          </div>
          {convs.map((c) => (
            <button key={c.id} className={`wa-item ${sel?.id === c.id ? "active" : ""}`} onClick={() => open(c.id)}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b>{c.name || "+" + c.wa_id}</b>
                {c.needs_human && <span className="badge warn">کارشناس</span>}
              </div>
              <div className="muted" style={{ fontSize: 13 }}>{c.last_message?.direction === "out" ? "↩ " : ""}{c.last_message?.body}</div>
            </button>
          ))}
          {!convs.length && <p className="muted" style={{ padding: 12 }}>گفتگویی نیست.</p>}
        </div>

        <div className="card">
          {!sel ? <p className="muted">یک گفتگو را انتخاب کنید.</p> : (
            <>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div>
                  <b>{sel.name}</b> <span className="muted ltr">+{sel.wa_id}</span>
                  <div className="muted" style={{ fontSize: 13 }}>ربات: {STATE[sel.state] || sel.state}
                    {sel.rfq && <> — درخواست <Link href={`/ops/rfq/${sel.rfq.id}`} className="ltr">{sel.rfq.reference}</Link> ({STATUSES[sel.rfq.status]})</>}
                  </div>
                </div>
                <div className="row">
                  {sel.state === "handoff"
                    ? <button className="secondary" onClick={() => patch({ bot_paused: false })}>واگذاری به ربات</button>
                    : <button className="secondary" onClick={() => patch({ bot_paused: true })}>توقف ربات و پاسخ دستی</button>}
                  {sel.needs_human && <button className="secondary" onClick={() => patch({ needs_human: false })}>رسیدگی شد</button>}
                </div>
              </div>
              <div className="wa-thread">
                {sel.messages.map((m) => (
                  <div key={m.id} className={`bubble ${m.direction}`}>
                    <div style={{ whiteSpace: "pre-wrap" }}>{m.body}</div>
                    <div className="meta">
                      {m.direction === "out" && (m.sender === "bot" ? "ربات" : m.sender)} · {new Date(m.at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
                      {m.delivery === "failed" && " · ارسال نشد"}{m.delivery === "logged" && " · (واتس‌اپ پیکربندی نشده)"}
                    </div>
                  </div>
                ))}
                <div ref={bottom} />
              </div>
              <form className="row" onSubmit={send}>
                <textarea rows={2} style={{ flex: 1 }} value={text} onChange={(e) => setText(e.target.value)}
                  placeholder={sel.window_open ? "پاسخ به مشتری…" : "پنجره ۲۴ ساعته بسته است"} disabled={!sel.window_open} />
                <button disabled={!text.trim() || !sel.window_open}>ارسال</button>
              </form>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
