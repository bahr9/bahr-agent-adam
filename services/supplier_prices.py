# -*- coding: utf-8 -*-
"""
🏬 أسعار الموردين -- سعر السوق جنب سعر أحمد، ومايتخلطوش أبدًا.

المورد المدعوم: **ماحجوب** (سيراميك وبورسلين وأدوات صحية ومطابخ).

عزيز صلاب اتفحص واتشال عن قصد (2026-08-08): الموقع بيرجّع 4,267 بايت لكل
رابط -- نفس الحجم للرئيسية وللقسم وللمنتج -- يعني قشرة وكل حاجة بتترسم
بجافاسكريبت. مفيش قراءة من غيرمتصفح كامل، وقرار أحمد إن ماحجوب يكفي كبداية.

## ليه JSON مش قراءة HTML

ماحجوب شغال على Salesforce Commerce Cloud، وفيه endpoint عام بيرجّع
المنتج JSON منظّم. الفرق مش رفاهية:

  - الأسعار بترجع **أرقام** (`613.8`) مش نصوص محتاجة تنضيف
  - **`Unit Of Measure`** جاي مع كل صنف -- فمفيش افتراض إن ده سعر متر.
    ده أخطر مصدر غلط في الموضوع كله: بورسلين بالمتر، وخلاط بالقطعة،
    والفرق بينهم في مقايسة بيبقى كارثة.
  - مش بيتكسر أول ما يغيّروا كلاسات الـCSS

البحث لسه HTML (بنستخرج منه أرقام الأصناف بس) لأن مفيش endpoint بحث عام
-- بس رقم الصنف موجود في الروابط نفسها، وده أثبت حاجة في أي صفحة.

## القاعدة الحاكمة: ده سعر معرض، مش سعر أحمد

الأرقام اللي بترجع من هنا **أسعار بيع للجمهور**. أحمد بيشتري بعلاقة وخصم
كمية، فالرقم ده مرجع سوق و**جرس** لما حاجة تتحرك -- مش أساس تسعير.

عشان كده الملف ده **قراءة بس، صفر كتابة**. مفيش سعر مورد بيدخل قاعدة
أسعار أحمد تلقائيًا. نفس مبدأ `source="plan"` في إمساك البلانات، بس
مطبّق بالشكل الأصرم: المصدر الخارجي ميدخلش أصلاً.
"""

import re

from utils.logger import logger

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

_SEARCH_URL = "https://www.mahgoub.com/en/search"
_PRODUCT_URL = ("https://www.mahgoub.com/on/demandware.store/"
                "Sites-mahgoub-Site/en_US/Product-ShowQuickView")

_TIMEOUT = 25
DEFAULT_LIMIT = 5
MAX_LIMIT = 10

SUPPLIER = "ماحجوب"


class SupplierError(Exception):
    """فشل قراءة من المورد -- بيتقال لأحمد صراحة مش بيتبلع."""


def _get(url, params):
    import requests
    return requests.get(
        url, params=params, timeout=_TIMEOUT,
        headers={"User-Agent": _UA, "Accept": "application/json,text/html;q=0.9"},
    )


def search_product_ids(query, limit=DEFAULT_LIMIT):
    """أرقام الأصناف المطابقة للبحث.

    البحث عند ماحجوب **إنجليزي بس** -- استعلام عربي بيرجّع صفر نتيجة
    (متجرّب 2026-08-08). الترجمة مسؤولية اللي بينده الأداة.
    """
    q = " ".join(str(query or "").split())
    if not q:
        return []
    try:
        response = _get(_SEARCH_URL, {"q": q})
    except Exception as e:
        raise SupplierError("مقدرتش أوصل لموقع " + SUPPLIER + ": " + str(e)[:70]) from e
    if response.status_code != 200:
        raise SupplierError(SUPPLIER + " رجّع HTTP " + str(response.status_code))

    html = response.text
    ids = re.findall(r"pid=(\d{6,})", html) or re.findall(r"-(\d{9,})\.html", html)
    unique = list(dict.fromkeys(ids))
    return unique[:max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))]


def _attr(product, label):
    """قيمة مواصفة بالاسم، أو None. القيم بترجع لستة حتى لو عنصر واحد."""
    for group in (product.get("attributes") or []):
        for attribute in (group.get("attributes") or []):
            if (attribute.get("label") or "").strip().casefold() == label.casefold():
                values = attribute.get("value")
                if isinstance(values, list):
                    return ", ".join(str(v) for v in values if v) or None
                return str(values) if values else None
    return None


def fetch_product(pid):
    """بيانات صنف واحد منظّمة. None لو فشل -- صنف واحد مش بيوقّع الباقي."""
    try:
        response = _get(_PRODUCT_URL, {"pid": str(pid)})
        product = (response.json() or {}).get("product") or {}
    except Exception as e:
        logger.warning("⚠️ صنف " + str(pid) + " من " + SUPPLIER + " فشل: " + str(e)[:70])
        return None
    if not product.get("productName"):
        return None

    price = product.get("price") or {}
    sales = (price.get("sales") or {}).get("value")
    listed = (price.get("list") or {}).get("value")

    # الصورة مش رفاهية هنا: أحمد بيختار خامة بالعين قبل الرقم، وبند
    # سيراميك من غير صورة اسم ورقم بس. بناخد أول لقطة كبيرة.
    image = None
    for size in ("large", "small"):
        shots = (product.get("images") or {}).get(size) or []
        if shots and isinstance(shots[0], dict) and shots[0].get("url"):
            image = shots[0]["url"]
            break

    return {
        "image": image,
        "id": product.get("id"),
        "name": product.get("productName"),
        "brand": _attr(product, "Brand"),
        "size": _attr(product, "Size"),
        "grade": _attr(product, "Grade"),
        "country": _attr(product, "Production Country"),
        # الوحدة **بتيجي من المورد** ومبتتفترضش أبدًا. غيابها بيتقال.
        "unit": _attr(product, "Unit Of Measure"),
        "price": sales if sales is not None else listed,
        "list_price": listed if (sales is not None and listed != sales) else None,
        "currency": ((price.get("sales") or price.get("list") or {}).get("currency")) or "EGP",
        "available": bool(product.get("available")),
    }


def _my_prices(query):
    """أسعار أحمد المطابقة للطلب -- مرجعه هو، مش المورد."""
    try:
        from services import price_base_service as pbs
        docs = pbs._all_docs_supabase_first()
        by_item = {d.get("item", ""): d for d in docs if d.get("item")}
        matched = pbs.search_items(query, list(by_item)) if query else []
        return [by_item[name] for name in matched]
    except Exception as e:
        logger.warning("⚠️ قراءة أسعار أحمد فشلت: " + str(e)[:70])
        return []


def _money(value, currency="EGP"):
    if value is None:
        return "؟"
    return ("{:,.2f}".format(float(value)).rstrip("0").rstrip(".")) + " " + currency


def format_comparison(query, products, mine, today):
    """التقرير: سعر أحمد الأول، وسعر المورد متعلّم إنه سعر معرض."""
    lines = []

    if mine:
        lines.append("💰 **سعرك المسجّل** (هو المرجع في أي مقايسة):")
        for doc in mine:
            unit = (" / " + doc.get("unit")) if doc.get("unit") else ""
            updated = str(doc.get("updated_at") or "")[:10]
            stamp = ("  — آخر تحديث " + updated) if updated else ""
            lines.append("   • " + str(doc.get("item")) + " = " + str(doc.get("price")) + unit + stamp)
    else:
        lines.append("💰 **مفيش سعر مسجّل عندك للبند ده** — اللي تحت مرجع سوق مش سعرك.")

    lines.append("")
    lines.append("🏬 **" + SUPPLIER + "** — بحث «" + query + "»، اتجاب " + today + ":")
    if not products:
        lines.append("   مفيش نتايج للبحث ده. جرّب كلمات إنجليزية أعم (البحث عندهم إنجليزي بس).")
    for item in products:
        head = "   • " + str(item["name"])
        bits = [b for b in (item.get("brand"), item.get("size"), item.get("grade"), item.get("country")) if b]
        if bits:
            head += "  [" + " · ".join(bits) + "]"
        lines.append(head)

        unit = item.get("unit")
        unit_text = (" / " + unit) if unit else " (⚠️ الوحدة مش مذكورة عند المورد)"
        price_line = "     " + _money(item.get("price"), item["currency"]) + unit_text
        if item.get("list_price"):
            price_line += "   (قبل الخصم " + _money(item["list_price"], item["currency"]) + ")"
        price_line += "   — " + ("متوفر" if item["available"] else "مش متوفر")
        lines.append(price_line)
        if item.get("image"):
            lines.append("     🖼 " + item["image"])

    lines.append("")
    lines.append(
        "⚠️ أسعار " + SUPPLIER + " دي **أسعار بيع للجمهور**، مش سعر شرا أحمد. "
        "استخدمها كمؤشر سوق أو لما فرق كبير يستاهل ينتبه له — "
        "وأي تسعير بيتبني على سعر أحمد المسجّل."
    )
    return "\n".join(lines)


def check_supplier_price(query, limit=DEFAULT_LIMIT, my_item=""):
    """يقارن سعر أحمد بأسعار المورد. قراءة بس -- صفر كتابة.

    `my_item` اسم البند في قاعدة أحمد **بالعربي**، منفصل عن `query`
    الإنجليزي. الفصل ده ضروري مش تزويق: بحث ماحجوب إنجليزي وبنود أحمد
    عربي، فالبحث بكلمة واحدة في الاتنين بيرجّع "مفيش سعر مسجّل عندك"
    وأحمد عنده السعر فعلاً -- والمقارنة، اللي هي الهدف كله، بتختفي
    بصمت (اتكشف في أول تشغيلة حقيقية 2026-08-08).
    """
    from utils.time_utils import now_cairo

    q = " ".join(str(query or "").split())
    if not q:
        return "قوللي البند اللي عايز تشوف سعره (بالإنجليزي، مثال: porcelain 60x120)."

    try:
        ids = search_product_ids(q, limit)
    except SupplierError as e:
        return "❌ " + str(e)

    products = [p for p in (fetch_product(pid) for pid in ids) if p]
    mine = _my_prices(my_item) or _my_prices(q)
    today = str(now_cairo())[:10]

    logger.info("🏬 " + SUPPLIER + ": «" + q + "» -> " + str(len(products)) + " صنف")
    return format_comparison(q, products, mine, today)
