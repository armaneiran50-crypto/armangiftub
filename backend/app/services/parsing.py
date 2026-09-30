"""Lightweight parsers for chat input (Persian / English): digits, countries, modes, weights, dates."""
import re
from datetime import date, timedelta

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789.,")

# Country names, major ports and cities → ISO-3166 alpha-2
COUNTRY_ALIASES = {
    "CN": ["چین", "china", "shanghai", "شانگهای", "ningbo", "نینگبو", "shenzhen", "شنژن", "guangzhou", "گوانگژو",
           "qingdao", "چینگدائو", "tianjin", "xiamen", "yiwu", "ییوو"],
    "AE": ["امارات", "uae", "emirates", "dubai", "دبی", "jebel ali", "جبل علی", "abu dhabi", "ابوظبی", "sharjah", "شارجه"],
    "SA": ["عربستان", "saudi", "ksa", "jeddah", "جده", "riyadh", "ریاض", "dammam", "دمام"],
    "QA": ["قطر", "qatar", "doha", "دوحه", "hamad"],
    "OM": ["عمان", "oman", "muscat", "مسقط", "sohar", "صحار"],
    "KW": ["کویت", "kuwait"],
    "BH": ["بحرین", "bahrain"],
    "TR": ["ترکیه", "turkey", "türkiye", "turkiye", "istanbul", "استانبول", "mersin", "مرسین", "izmir", "ازمیر"],
    "IN": ["هند", "india", "mumbai", "بمبئی", "nhava sheva", "mundra", "chennai"],
    "DE": ["آلمان", "germany", "hamburg", "هامبورگ"],
    "IT": ["ایتالیا", "italy", "genoa", "milan", "میلان"],
    "NL": ["هلند", "netherlands", "holland", "rotterdam", "روتردام"],
    "ES": ["اسپانیا", "spain", "valencia", "barcelona"],
    "GB": ["انگلستان", "انگلیس", "uk", "united kingdom", "england", "london", "لندن"],
    "US": ["آمریکا", "امریکا", "usa", "united states", "america"],
    "KR": ["کره", "korea", "busan", "بوسان"],
    "JP": ["ژاپن", "japan", "tokyo"],
    "VN": ["ویتنام", "vietnam", "ho chi minh", "haiphong"],
    "MY": ["مالزی", "malaysia", "port klang"],
    "IR": ["ایران", "iran", "bandar abbas", "بندرعباس", "بندر عباس", "tehran", "تهران"],
}

# Persian spellings of cities/ports → canonical English name
CITY_CANONICAL = {
    "شانگهای": "Shanghai", "نینگبو": "Ningbo", "شنژن": "Shenzhen", "گوانگژو": "Guangzhou", "چینگدائو": "Qingdao",
    "ییوو": "Yiwu", "دبی": "Dubai", "جبل علی": "Jebel Ali", "ابوظبی": "Abu Dhabi", "شارجه": "Sharjah", "جده": "Jeddah",
    "ریاض": "Riyadh", "دمام": "Dammam", "دوحه": "Doha", "مسقط": "Muscat", "صحار": "Sohar", "استانبول": "Istanbul",
    "مرسین": "Mersin", "ازمیر": "Izmir", "بمبئی": "Mumbai", "هامبورگ": "Hamburg", "میلان": "Milan", "روتردام": "Rotterdam",
    "لندن": "London", "بوسان": "Busan", "بندرعباس": "Bandar Abbas", "بندر عباس": "Bandar Abbas", "تهران": "Tehran",
}

MODE_ALIASES = {
    "ocean_fcl": ["fcl", "کانتینر کامل", "full container", "کانتینری", "کانتینر"],
    "ocean_lcl": ["lcl", "خرده", "خرده‌بار", "خرده بار", "less than container", "groupage"],
    "air": ["هوایی", "air", "هواپیما", "airfreight", "air freight"],
    "road": ["زمینی", "road", "truck", "کامیون", "trucking"],
}
MODE_MENU = {"1": "ocean_fcl", "2": "ocean_lcl", "3": "air", "4": "road"}


def normalize(text: str) -> str:
    return text.translate(_FA_DIGITS).replace("ي", "ی").replace("ك", "ک").strip()


def is_persian(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text or ""))


_NOT_CITIES = {"uae", "usa", "uk", "ksa", "emirates", "united kingdom", "united states", "america", "england",
               "holland", "türkiye", "turkiye"}
_WORD = r"\w"  # covers Persian letters too; punctuation such as ، stays a boundary


def find_countries(text: str) -> list[tuple[str, str | None]]:
    """All (country_code, city/port or None) mentioned, in order of appearance, one per country."""
    t = normalize(text).lower()
    hits: dict[str, tuple[int, str | None]] = {}
    for code, aliases in COUNTRY_ALIASES.items():
        for i, a in enumerate(aliases):
            m = re.search(rf"(?<!{_WORD}){re.escape(a)}(?!{_WORD})", t)
            if not m:
                continue
            city = CITY_CANONICAL.get(a) or (a.title() if i > 0 and not is_persian(a) and a not in _NOT_CITIES else None)
            prev = hits.get(code)
            if prev is None or m.start() < prev[0]:
                hits[code] = (m.start(), city or (prev[1] if prev else None))
            elif city and not prev[1]:
                hits[code] = (prev[0], city)
    return [(code, city) for code, (_, city) in sorted(hits.items(), key=lambda kv: kv[1][0])]


def find_country(text: str) -> tuple[str, str | None] | None:
    """Return the first (country_code, matched city/port or None)."""
    t = normalize(text).strip()
    if re.fullmatch(r"[A-Za-z]{2}", t) and t.upper() in COUNTRY_ALIASES:
        return t.upper(), None
    found = find_countries(text)
    return found[0] if found else None


def find_mode(text: str) -> str | None:
    t = normalize(text).lower()
    if t in MODE_MENU:
        return MODE_MENU[t]
    for mode, aliases in MODE_ALIASES.items():
        if any(a in t for a in aliases):
            return mode
    return None


def find_weight_kg(text: str) -> float | None:
    t = normalize(text).lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(tons?|tonnes?|t\b|تن)", t)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kgs|کیلو|کیلوگرم)?", t)
    return float(m.group(1)) if m and float(m.group(1)) > 0 else None


def find_volume_cbm(text: str) -> float | None:
    t = normalize(text).lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m and float(m.group(1)) > 0 else None


_CONTAINER_TYPES = {"20": "20GP", "40": "40GP", "40hc": "40HC", "45": "45HC", "45hc": "45HC", "20rf": "20RF", "40rf": "40RF",
                    "20gp": "20GP", "40gp": "40GP", "20dv": "20GP", "40dv": "40GP", "40hq": "40HC"}


def find_containers(text: str) -> str | None:
    """'2x40HC', '2 تا 40 فوت', '1 x 20' → '2x40HC' / '1x20GP'."""
    t = normalize(text).lower().replace("فوت", "").replace("foot", "").replace("ft", "").replace("'", "")
    t = t.replace("high cube", "hc").replace("های کیوب", "hc")
    parts = []
    t = re.sub(r"\b(containers?|cntrs?)\b|کانتینر", " ", t)
    for m in re.finditer(r"(?<![\d/.-])(\d{1,3})\s*(?:x|×|\*|تا|عدد)?\s*(20|40|45)(?![\d/.-])\s*(hc|hq|gp|dv|rf)?", t):
        qty, size, kind = m.group(1), m.group(2), m.group(3) or ""
        ctype = _CONTAINER_TYPES.get(size + kind) or _CONTAINER_TYPES.get(size)
        if int(qty) > 0:
            parts.append(f"{int(qty)}x{ctype}")
    if not parts:
        m = re.fullmatch(r"\s*(20|40|45)\s*(hc|hq|gp|dv|rf)?\s*", t)
        if m:
            parts.append(f"1x{_CONTAINER_TYPES.get(m.group(1) + (m.group(2) or '')) or _CONTAINER_TYPES[m.group(1)]}")
    return ",".join(parts) or None


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    months = [0, 31, 29 if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and gd > months[gm]:
        gd -= months[gm]
        gm += 1
    return date(gy, gm, gd)


def find_date(text: str, today: date | None = None) -> str | None:
    """ISO date from 'YYYY-MM-DD', Jalali '1405/08/20', 'DD/MM/YYYY', or 'asap'/'فوری'."""
    today = today or date.today()
    t = normalize(text).lower()
    if any(w in t for w in ("asap", "فوری", "همین هفته", "this week", "urgent")):
        return (today + timedelta(days=3)).isoformat()
    if any(w in t for w in ("next week", "هفته بعد", "هفته آینده")):
        return (today + timedelta(days=7)).isoformat()
    m = re.search(r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})", t)
    try:
        if m:
            y, mo, d = map(int, m.groups())
            return (jalali_to_gregorian(y, mo, d) if y < 1700 else date(y, mo, d)).isoformat()
        m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", t)
        if m:
            d, mo, y = map(int, m.groups())
            return (jalali_to_gregorian(y, mo, d) if y < 1700 else date(y, mo, d)).isoformat()
    except ValueError:
        return None
    return None


def find_email(text: str) -> str | None:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return m.group(0) if m else None
