"use client";

import { useState } from "react";

export default function Login({ onLogin, title = "ورود به پنل عملیات" }: { onLogin: (email: string, password: string) => Promise<void>; title?: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin(email, password);
    } catch {
      setError("ایمیل یا رمز عبور اشتباه است.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 420, margin: "48px auto" }} onSubmit={submit}>
      <h2>{title}</h2>
      <div style={{ marginTop: 12 }}><label>ایمیل</label><input dir="ltr" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
      <div style={{ marginTop: 12 }}><label>رمز عبور</label><input dir="ltr" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
      {error && <div className="alert err">{error}</div>}
      <div className="actions"><button disabled={busy}>ورود</button></div>
    </form>
  );
}
