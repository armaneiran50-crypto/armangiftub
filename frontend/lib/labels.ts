export const MODES: Record<string, string> = {
  ocean_fcl: "دریایی کانتینر کامل (FCL)",
  ocean_lcl: "دریایی خرده‌بار (LCL)",
  air: "هوایی",
  road: "زمینی",
};

export const STATUSES: Record<string, string> = {
  started: "ناقص",
  qualified: "آماده ارسال",
  compliance_hold: "بررسی انطباق",
  dispatched: "ارسال‌شده به شرکت‌ها",
  quoted: "دارای پیشنهاد قیمت",
  booked: "رزرو شده",
  closed: "تحویل و بسته شده",
  rejected: "رد شده",
};

export const FIELDS: Record<string, string> = {
  origin_country: "کشور مبدأ",
  destination_country: "کشور مقصد",
  mode: "نوع حمل",
  commodity: "نوع کالا",
  weight_kg: "وزن",
  ready_date: "تاریخ آمادگی بار",
  contact_email: "ایمیل",
  containers: "تعداد و نوع کانتینر",
  volume_cbm: "حجم (CBM)",
};

export const CARGO_CLASSES: Record<string, string> = {
  general: "عمومی",
  dg: "خطرناک (DG)",
  reefer: "یخچالی",
  oversized: "حجیم / فوق‌سنگین",
  fragile: "شکستنی",
  high_value: "ارزش بالا",
};

export const LABELS: Record<string, string> = {
  cheapest: "ارزان‌ترین",
  fastest: "سریع‌ترین",
  most_complete: "کامل‌ترین",
};

export const COUNTRIES: [string, string][] = [
  ["CN", "چین"], ["AE", "امارات"], ["SA", "عربستان"], ["QA", "قطر"], ["OM", "عمان"], ["KW", "کویت"], ["BH", "بحرین"],
  ["TR", "ترکیه"], ["IN", "هند"], ["DE", "آلمان"], ["IT", "ایتالیا"], ["NL", "هلند"], ["ES", "اسپانیا"], ["GB", "انگلستان"],
  ["US", "آمریکا"], ["KR", "کره جنوبی"], ["JP", "ژاپن"], ["VN", "ویتنام"], ["MY", "مالزی"], ["IR", "ایران"],
];

export const countryName = (code?: string | null) => COUNTRIES.find(([c]) => c === code)?.[1] || code || "—";
export const fa = (n: number | null | undefined, digits = 0) =>
  n == null ? "—" : n.toLocaleString("fa-IR", { maximumFractionDigits: digits });
