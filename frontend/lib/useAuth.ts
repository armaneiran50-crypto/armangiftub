"use client";

import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

export type Me = { id: number; email: string; role: string };

export function useAuth() {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api<Me>("/api/auth/me", { auth: true })
      .then(setMe)
      .catch(() => setToken(null))
      .finally(() => setReady(true));
  }, []);

  async function login(email: string, password: string) {
    const r = await api<{ access_token: string }>("/api/auth/login", {
      form: new URLSearchParams({ username: email, password }),
    });
    setToken(r.access_token);
    setMe(await api<Me>("/api/auth/me", { auth: true }));
  }

  function logout() {
    setToken(null);
    setMe(null);
  }

  return { me, ready, login, logout };
}
