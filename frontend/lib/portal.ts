export type PortalRFQ = {
  rfq_id: number; reference: string; lane: string; origin_city: string | null; destination_city: string | null;
  mode: string | null; commodity: string | null; cargo_class: string | null; weight_kg: number | null;
  volume_cbm: number | null; containers: string | null; incoterm: string | null; ready_date: string | null;
  dispatched_at: string; state: string; open: boolean;
};
export const PORTAL_STATES: Record<string, [string, string]> = {
  pending: ["منتظر قیمت شما", "brand"],
  quoted: ["قیمت ارسال شد", ""],
  declined: ["انصراف داده‌اید", ""],
  won: ["برنده شدید", "ok"],
  lost: ["انتخاب نشد", "err"],
  closed: ["بسته شده", ""],
};
