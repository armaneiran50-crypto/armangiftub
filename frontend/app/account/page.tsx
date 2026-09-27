"use client";

import { useState } from "react";
import Login from "@/components/Login";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function Account() {
  const { me, ready, login } = useAuth();
  const [f, setF] = useState({ current: "", next: "", repeat: "" });
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  if (!ready) return null;
  if (!me) return <main className="container"><Login onLogin={login} /></main>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (f.next !== f.repeat) return setMsg({ kind: "err", text: "تکرار رمز جدید مطابقت ندارد." });
    try {
      await api("/api/auth/password", { auth: true, body: { current_password: f.current, new_password: f.next } });
      setMsg({ kind: "ok", text: "رمز عبور تغییر کرد." });
      setF({ current: "", next: "", repeat: "" });
    } catch (err) {
      setMsg({ kind: "err", text: (err as Error).message === "Current password is incorrect" ? "رمز فعلی اشتباه است." : (err as Error).message });
    }
  }

  return (
    <main className="container">
      <form className="card" style={{ maxWidth: 420, margin: "48px auto" }} onSubmit={submit}>
        <h2>تغییر رمز عبور</h2>
        <p className="sub ltr">{me.email}</p>
        <div style={{ marginTop: 12 }}><label>رمز فعلی</label><input type="password" dir="ltr" required value={f.current} onChange={(e) => setF({ ...f, current: e.target.value })} /></div>
        <div style={{ marginTop: 12 }}><label>رمز جدید (حداقل ۸ کاراکتر)</label><input type="password" dir="ltr" minLength={8} required value={f.next} onChange={(e) => setF({ ...f, next: e.target.value })} /></div>
        <div style={{ marginTop: 12 }}><label>تکرار رمز جدید</label><input type="password" dir="ltr" minLength={8} required value={f.repeat} onChange={(e) => setF({ ...f, repeat: e.target.value })} /></div>
        {msg && <div className={`alert ${msg.kind}`}>{msg.text}</div>}
        <div className="actions"><button>ذخیره</button></div>
      </form>
    </main>
  );
}
