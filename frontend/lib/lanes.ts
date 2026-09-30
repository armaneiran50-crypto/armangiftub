/**
 * Lane pages (masterplan §15). Each page must carry unique, useful information; a page is only
 * indexed by search engines once `reviewed` is set to true after an editorial/operations check.
 * Transit times are indicative ranges and must be reviewed against real quotes.
 */
export type ModeInfo = { mode: "ocean_fcl" | "ocean_lcl" | "air" | "road"; transit: string; note: string };
export type Lane = {
  slug: string;
  origin: string; // ISO code
  destination: string;
  originName: string;
  destinationName: string;
  reviewed: boolean;
  title: string;
  description: string;
  intro: string;
  ports: { origin: string[]; destination: string[] };
  modes: ModeInfo[];
  documents: string[];
  tips: string[];
  faq: { q: string; a: string }[];
};

const COMMON_DOCS = [
  "فاکتور تجاری (Commercial Invoice)",
  "لیست بسته‌بندی (Packing List)",
  "بارنامه دریایی (B/L) یا هوایی (AWB) یا بارنامه جاده‌ای (CMR)",
  "گواهی مبدأ (Certificate of Origin) در صورت نیاز کشور مقصد یا استفاده از معافیت تعرفه‌ای",
];

export const LANES: Lane[] = [
  {
    slug: "china-to-uae",
    origin: "CN", destination: "AE", originName: "چین", destinationName: "امارات",
    reviewed: false,
    title: "حمل بار از چین به امارات (دبی و جبل علی)",
    description: "حمل دریایی FCL و LCL و هوایی از شانگهای، نینگبو، شنژن و گوانگژو به جبل علی و دبی؛ زمان تقریبی ترانزیت، مدارک و دریافت چند پیشنهاد قیمت.",
    intro: "چین بزرگ‌ترین مبدأ واردات امارات است و مسیر بنادر شرق چین به جبل علی از پرتردد‌ترین مسیرهای کانتینری منطقه است. بیشتر محموله‌ها به‌صورت کانتینر کامل (FCL) یا خرده‌بار (LCL) از طریق دریا جابه‌جا می‌شوند و بار فوری یا کم‌حجم با پرواز به دبی ارسال می‌شود.",
    ports: { origin: ["Shanghai", "Ningbo", "Shenzhen (Yantian/Shekou)", "Guangzhou (Nansha)", "Qingdao"], destination: ["Jebel Ali", "Khalifa Port (Abu Dhabi)", "Sharjah", "DXB / DWC (هوایی)"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۱۸ تا ۲۸ روز بندر به بندر", note: "بسته به بندر بارگیری، مستقیم بودن سرویس و شلوغی بنادر." },
      { mode: "ocean_lcl", transit: "حدود ۲۵ تا ۳۵ روز", note: "زمان تجمیع در انبار مبدأ و تفکیک در مقصد به ترانزیت اضافه می‌شود." },
      { mode: "air", transit: "حدود ۲ تا ۵ روز فرودگاه به فرودگاه", note: "مناسب بار فوری، نمونه و کالای با ارزش بالا." },
    ],
    documents: [...COMMON_DOCS, "کد واردکننده / مجوز تجاری در امارات برای ترخیص"],
    tips: [
      "برای بار بیش از حدود ۱۵ متر مکعب، مقایسه قیمت LCL با یک کانتینر ۲۰ فوت معمولاً ارزش دارد.",
      "هزینه‌های مبدأ (THC، اسناد) و مقصد (DTHC، ترخیص، تحویل) را جدا از کرایه اصلی مقایسه کنید.",
      "ایام تعطیلات سال نوی چینی ظرفیت و زمان بارگیری را به‌شدت تحت تأثیر قرار می‌دهد.",
    ],
    faq: [
      { q: "حمل از چین به دبی چقدر طول می‌کشد؟", a: "برای FCL معمولاً حدود ۱۸ تا ۲۸ روز بندر به بندر و برای هوایی ۲ تا ۵ روز؛ زمان دقیق در پیشنهادهای قیمت هر شرکت ذکر می‌شود." },
      { q: "FCL بهتر است یا LCL؟", a: "وقتی حجم بار به نصف کانتینر ۲۰ فوت نزدیک می‌شود، FCL اغلب اقتصادی‌تر و سریع‌تر است. با ماشین‌حساب CBM حجم را محاسبه کنید." },
      { q: "آیا ترخیص در دبی هم انجام می‌شود؟", a: "بسیاری از شرکت‌های حمل خدمات ترخیص و تحویل درب‌به‌درب را هم ارائه می‌دهند؛ در درخواست خود اینکوترمز و محل تحویل را مشخص کنید." },
    ],
  },
  {
    slug: "china-to-saudi-arabia",
    origin: "CN", destination: "SA", originName: "چین", destinationName: "عربستان سعودی",
    reviewed: false,
    title: "حمل بار از چین به عربستان سعودی (جده، دمام، ریاض)",
    description: "حمل کانتینری و هوایی از بنادر چین به جده و دمام و تحویل در ریاض؛ زمان تقریبی، مدارک و الزامات ثبت محصول.",
    intro: "عربستان بزرگ‌ترین بازار مصرف حوزه خلیج فارس است. محموله‌های چین برای غرب عربستان معمولاً به جده و برای شرق و ریاض به دمام می‌روند. الزامات انطباق محصول در عربستان باید پیش از حمل بررسی شود.",
    ports: { origin: ["Shanghai", "Ningbo", "Shenzhen", "Qingdao"], destination: ["Jeddah Islamic Port", "King Abdulaziz Port (Dammam)", "Riyadh Dry Port"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۲۰ تا ۳۰ روز بندر به بندر", note: "سرویس‌های جده و دمام متفاوت‌اند؛ مقصد نهایی را دقیق مشخص کنید." },
      { mode: "ocean_lcl", transit: "حدود ۲۸ تا ۴۰ روز", note: "" },
      { mode: "air", transit: "حدود ۳ تا ۶ روز", note: "" },
    ],
    documents: [...COMMON_DOCS, "گواهی انطباق محصول (سامانه SABER) برای کالاهای مشمول"],
    tips: [
      "پیش از خرید، مشمول بودن کالا در الزامات SABER را بررسی کنید؛ نبود گواهی باعث توقف بار در گمرک می‌شود.",
      "برای تحویل در ریاض، هزینه حمل زمینی از دمام یا ارسال مستقیم به بندر خشک ریاض را مقایسه کنید.",
    ],
    faq: [
      { q: "بار چین به ریاض از کدام بندر برود؟", a: "معمولاً دمام و سپس حمل ریلی یا جاده‌ای؛ برخی سرویس‌ها مستقیم تا بندر خشک ریاض بارنامه صادر می‌کنند." },
      { q: "گواهی SABER چیست؟", a: "سامانه انطباق محصولات عربستان است که برای بسیاری از کالاها قبل از ترخیص لازم است." },
    ],
  },
  {
    slug: "china-to-qatar",
    origin: "CN", destination: "QA", originName: "چین", destinationName: "قطر",
    reviewed: false,
    title: "حمل بار از چین به قطر (بندر حمد)",
    description: "حمل دریایی و هوایی از چین به بندر حمد و دوحه؛ سرویس مستقیم یا با ترانشیپ، زمان تقریبی و مدارک.",
    intro: "بار چین به قطر یا با سرویس مستقیم به بندر حمد می‌رسد یا از طریق بنادر ترانشیپ منطقه. نوع سرویس روی زمان و قیمت اثر زیادی دارد و در مقایسه پیشنهادها باید دیده شود.",
    ports: { origin: ["Shanghai", "Ningbo", "Shenzhen", "Qingdao"], destination: ["Hamad Port", "DOH (هوایی)"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۲۰ تا ۳۵ روز", note: "سرویس با ترانشیپ معمولاً طولانی‌تر است." },
      { mode: "ocean_lcl", transit: "حدود ۲۸ تا ۴۰ روز", note: "" },
      { mode: "air", transit: "حدود ۲ تا ۵ روز", note: "" },
    ],
    documents: [...COMMON_DOCS],
    tips: ["در مقایسه پیشنهادها، مستقیم یا ترانشیپ بودن سرویس و بندر ترانشیپ را بپرسید."],
    faq: [{ q: "آیا سرویس مستقیم چین به قطر وجود دارد؟", a: "بله برخی خطوط سرویس مستقیم دارند و بقیه از طریق بنادر منطقه ترانشیپ می‌کنند؛ این مورد در پیشنهاد هر شرکت مشخص می‌شود." }],
  },
  {
    slug: "india-to-uae",
    origin: "IN", destination: "AE", originName: "هند", destinationName: "امارات",
    reviewed: false,
    title: "حمل بار از هند به امارات (نهاوا شوا و موندرا به جبل علی)",
    description: "حمل دریایی کوتاه‌مسیر و هوایی از بنادر غربی هند به جبل علی؛ زمان تقریبی، مدارک و نکات.",
    intro: "مسیر هند به امارات کوتاه و پرتردد است و سرویس‌های دریایی مکرری از بنادر غربی هند به جبل علی وجود دارد؛ برای همین زمان ترانزیت کوتاه و رقابت قیمتی بالاست.",
    ports: { origin: ["Nhava Sheva (JNPT)", "Mundra", "Chennai", "Cochin"], destination: ["Jebel Ali", "Khalifa Port", "Sharjah"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۴ تا ۸ روز از بنادر غربی", note: "از بنادر شرقی هند طولانی‌تر است." },
      { mode: "ocean_lcl", transit: "حدود ۷ تا ۱۴ روز", note: "" },
      { mode: "air", transit: "حدود ۱ تا ۳ روز", note: "" },
    ],
    documents: [...COMMON_DOCS],
    tips: ["به دلیل ترانزیت کوتاه، زمان آماده شدن اسناد و ترخیص سهم بزرگی از کل زمان را دارد؛ اسناد را زودتر آماده کنید."],
    faq: [{ q: "حمل از هند به دبی چند روز است؟", a: "از نهاوا شوا یا موندرا معمولاً حدود یک هفته بندر به بندر؛ هوایی ۱ تا ۳ روز." }],
  },
  {
    slug: "turkey-to-uae",
    origin: "TR", destination: "AE", originName: "ترکیه", destinationName: "امارات",
    reviewed: false,
    title: "حمل بار از ترکیه به امارات",
    description: "حمل دریایی از مرسین و استانبول به جبل علی و حمل هوایی؛ زمان تقریبی، مدارک و نکات مسیر.",
    intro: "کالاهای ترکیه (مصالح ساختمانی، منسوجات، مواد غذایی و ماشین‌آلات) سهم بزرگی در واردات امارات دارند. حمل دریایی معمولاً از مرسین یا بنادر مرمره انجام می‌شود و مسیر آن به وضعیت دریای سرخ و کانال سوئز حساس است.",
    ports: { origin: ["Mersin", "Istanbul (Ambarli)", "Izmir", "Gemlik"], destination: ["Jebel Ali", "Khalifa Port"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۱۵ تا ۳۵ روز", note: "در صورت اختلال در دریای سرخ، مسیر و زمان تغییر می‌کند." },
      { mode: "ocean_lcl", transit: "حدود ۲۵ تا ۴۰ روز", note: "" },
      { mode: "air", transit: "حدود ۱ تا ۳ روز", note: "" },
    ],
    documents: [...COMMON_DOCS],
    tips: ["در زمان اختلال مسیرهای دریایی، زمان ترانزیت و سرشارژهای اضطراری (مانند War Risk) را در پیشنهادها دقیق مقایسه کنید."],
    faq: [{ q: "چه عاملی بیشترین اثر را روی زمان حمل ترکیه به امارات دارد؟", a: "مسیر کشتی (از سوئز یا دور آفریقا) و ترانشیپ؛ این موارد را از هر شرکت حمل بپرسید." }],
  },
  {
    slug: "turkey-to-saudi-arabia",
    origin: "TR", destination: "SA", originName: "ترکیه", destinationName: "عربستان سعودی",
    reviewed: false,
    title: "حمل بار از ترکیه به عربستان سعودی",
    description: "حمل دریایی از بنادر ترکیه به جده و دمام، حمل هوایی و زمینی؛ زمان تقریبی و مدارک.",
    intro: "بار ترکیه به غرب عربستان معمولاً دریایی به جده می‌رود و برای برخی محموله‌ها حمل زمینی یا هوایی هم گزینه است. الزامات انطباق محصول عربستان در این مسیر هم اعمال می‌شود.",
    ports: { origin: ["Mersin", "Istanbul (Ambarli)", "Iskenderun"], destination: ["Jeddah Islamic Port", "Dammam"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۱۰ تا ۲۵ روز به جده", note: "" },
      { mode: "road", transit: "حدود ۷ تا ۱۲ روز", note: "بسته به مسیر ترانزیت و تشریفات مرزی." },
      { mode: "air", transit: "حدود ۱ تا ۳ روز", note: "" },
    ],
    documents: [...COMMON_DOCS, "گواهی انطباق محصول (سامانه SABER) برای کالاهای مشمول"],
    tips: ["برای حمل زمینی، مجوزهای عبور و زمان توقف در مرزها را در پیشنهاد قیمت بپرسید."],
    faq: [{ q: "حمل زمینی از ترکیه به عربستان امکان‌پذیر است؟", a: "بله برای برخی محموله‌ها؛ زمان و هزینه به مسیر ترانزیت و تشریفات مرزی بستگی دارد." }],
  },
  {
    slug: "europe-to-uae",
    origin: "DE", destination: "AE", originName: "اروپا (آلمان)", destinationName: "امارات",
    reviewed: false,
    title: "حمل بار از اروپا (آلمان، هلند، ایتالیا) به امارات",
    description: "حمل کانتینری از هامبورگ، روتردام و جنوا به جبل علی و حمل هوایی؛ زمان تقریبی، مدارک و نکات.",
    intro: "ماشین‌آلات، قطعات و کالاهای صنعتی اروپا عمدتاً از بنادر شمال اروپا یا مدیترانه به جبل علی ارسال می‌شوند. مسیر سوئز یا دور آفریقا اثر زیادی روی زمان دارد.",
    ports: { origin: ["Hamburg", "Rotterdam", "Antwerp", "Genoa"], destination: ["Jebel Ali", "Khalifa Port"] },
    modes: [
      { mode: "ocean_fcl", transit: "حدود ۲۰ تا ۴۵ روز", note: "مسیر دور آفریقا حدود ۱۰ تا ۱۴ روز اضافه می‌کند." },
      { mode: "ocean_lcl", transit: "حدود ۳۰ تا ۵۰ روز", note: "" },
      { mode: "air", transit: "حدود ۱ تا ۳ روز", note: "" },
    ],
    documents: [...COMMON_DOCS, "گواهی EUR.1 یا مدارک مبدأ در صورت استفاده از موافقت‌نامه‌های تجاری"],
    tips: ["برای ماشین‌آلات، ابعاد و وزن دقیق و نیاز به کانتینر Open Top یا Flat Rack را در درخواست ذکر کنید."],
    faq: [{ q: "بار اروپا به دبی چقدر طول می‌کشد؟", a: "بسته به بندر و مسیر، حدود ۳ تا ۶ هفته دریایی و ۱ تا ۳ روز هوایی." }],
  },
  {
    slug: "uae-to-oman",
    origin: "AE", destination: "OM", originName: "امارات", destinationName: "عمان",
    reviewed: false,
    title: "حمل بار از امارات به عمان (زمینی و دریایی)",
    description: "حمل جاده‌ای از دبی و جبل علی به مسقط و صحار؛ زمان تقریبی، مدارک گمرکی و نکات مرزی.",
    intro: "امارات هاب توزیع منطقه است و بسیاری از محموله‌ها پس از ورود به جبل علی با کامیون به عمان و سایر کشورهای شورای همکاری ارسال می‌شوند. حمل زمینی در این مسیر سریع و رایج است.",
    ports: { origin: ["Jebel Ali", "Dubai", "Sharjah"], destination: ["Muscat", "Sohar", "Salalah"] },
    modes: [
      { mode: "road", transit: "حدود ۱ تا ۳ روز", note: "بسته به مقصد نهایی و زمان توقف در مرز." },
      { mode: "ocean_fcl", transit: "حدود ۲ تا ۵ روز فیدر", note: "" },
    ],
    documents: [...COMMON_DOCS, "اظهارنامه صادرات/ترانزیت امارات", "کارت گمرکی واردکننده در عمان"],
    tips: ["برای بار ترانزیتی که از خارج وارد جبل علی شده، اظهارنامه ترانزیت را از قبل هماهنگ کنید."],
    faq: [{ q: "حمل زمینی دبی به مسقط چند روز است؟", a: "معمولاً ۱ تا ۳ روز شامل تشریفات مرزی." }],
  },
];

export const laneBySlug = (slug: string) => LANES.find((l) => l.slug === slug);
