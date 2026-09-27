"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function WhatsAppButton() {
  const [number, setNumber] = useState<string | null>(null);
  useEffect(() => {
    api<{ whatsapp_number: string | null }>("/api/config").then((c) => setNumber(c.whatsapp_number)).catch(() => {});
  }, []);
  if (!number) return null;
  const text = encodeURIComponent("سلام، برای حمل بار قیمت می‌خواهم");
  return <a className="wa-float" href={`https://wa.me/${number.replace(/\D/g, "")}?text=${text}`} target="_blank" rel="noopener">واتس‌اپ</a>;
}
