"use client";

import { usePublicConfig } from "@/lib/useConfig";

export default function WhatsAppButton() {
  const number = usePublicConfig()?.whatsapp_number;
  if (!number) return null;
  const text = encodeURIComponent("سلام، برای حمل بار قیمت می‌خواهم");
  return <a className="wa-float" href={`https://wa.me/${number.replace(/\D/g, "")}?text=${text}`} target="_blank" rel="noopener">واتس‌اپ</a>;
}
