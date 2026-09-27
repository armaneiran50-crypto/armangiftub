"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

type PublicConfig = { whatsapp_number: string | null; ai_intake: boolean };
let cached: Promise<PublicConfig> | null = null;

export function usePublicConfig(): PublicConfig | null {
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  useEffect(() => {
    cached ??= api<PublicConfig>("/api/config").catch(() => ({ whatsapp_number: null, ai_intake: false }));
    cached.then(setCfg);
  }, []);
  return cfg;
}

/** AI features are only shown when the backend has them enabled. */
export const useAiEnabled = () => usePublicConfig()?.ai_intake ?? false;
