# -*- coding: utf-8 -*-
"""
💰 تسجيل الأسعار بالجملة -- الليستة كلها في نداء واحد بدل بند كل مرة.

الفجوة (2026-08-08): `save_price` بند واحد في المرة. عشان أحمد يدخّل قايمة
مقايسة حقيقية (60-80 بند بين خامات ومصنعيات) كان محتاج 80 محادثة -- فقاعدة
الأسعار وقفت عند 9 بنود، وهي أكبر حد على أي تقدير تكلفة آدم بيعمله.

المدخل هنا **مش نص حر**: آدم بيبعت بنود منظّمة، لأنه أصلاً بيكون قارئ
الليستة (نص ملزوق، أو صورة كشكول قراها بالـvision، أو ملف). فمفيش تمريرة
تهيكِل تانية زي البلانات -- التهيكِل بيحصل في نفس الدور.

## الفخ اللي الملف ده اتكتب عشانه

`save_price` لما السعر مايتفهمش كرقم بيسجّله في Firestore و**بيتخطى
Supabase** بتحذير في اللوج بس. والقراءة Supabase-first من هجرة 2026-08-06.
يعني البند بيتسجّل و**يختفي** -- أحمد يشوف "اتسجل" وبعدين ميلاقهوش.

في بند واحد ده مزعج؛ في ليستة 60 بند ده كارثة صامتة. فهنا السعر بيتفحص
**قبل** الحفظ، واللي مش مفهوم بيترفض ويتقال بالاسم -- مش بيتحفظ نص التحفيظ.

## التقرير هو نص المنتَج

أخطر لحظة في المسار ده مش الحفظ -- هي **تحديث سعر موجود برقم غلط** (صفر
ناقص من صورة مش واضحة). فالتقرير بيفصل الجديد عن **المتغيّر**، وبيوري
القديم جنب الجديد عشان أحمد يمسك الغلط في نفس اللحظة مش في مقايسة عميل.
"""

from utils.logger import logger

# سقف البند الواحد في النداء. الرقم كبير كفاية لأي مقايسة حقيقية، وموجود
# كحاجز ضد نداء بايظ مش كتقييد على أحمد. اللي فوقه بيتقال صراحة -- مفيش
# قص صامت (بند مقصوص بصمت = رقم ناقص في مقايسة محدش واخد باله منه).
MAX_ITEMS = 120


def _price_is_usable(price):
    """السعر ده هيوصل Supabase ولا هيختفي؟ الفحص اللي `save_price` مبيعملهوش قبل الكتابة."""
    try:
        from migration_transform import parse_price_range
        parse_price_range(price, "bulk_price")
        return True
    except Exception:
        return False


def validate_items(items):
    """يفصل البنود الصالحة عن المرفوضة. pure -- مفيش I/O.

    بيرجع (accepted, rejected) والـrejected لستة (اسم، سبب) عشان التقرير
    يقول **إيه** اترفض و**ليه**، مش رقم مجمّع.
    """
    accepted, rejected = [], []
    seen = {}

    for raw in (items or [])[:MAX_ITEMS]:
        if not isinstance(raw, dict):
            rejected.append(("(بند مش مفهوم)", "الشكل غلط"))
            continue

        item = " ".join(str(raw.get("item") or "").split())
        price = str(raw.get("price") or "").strip()

        if not item:
            rejected.append(("(من غير اسم)", "مفيش اسم بند"))
            continue
        if not price:
            rejected.append((item, "مفيش سعر"))
            continue
        if not _price_is_usable(price):
            rejected.append((item, 'السعر مش مفهوم كرقم أو مدى: "' + price + '"'))
            continue

        # نفس البند مرتين في نفس الليستة: الأخير بيغلب، بس بنقول
        # عشان مايعدّيش كأن الاتنين اتسجلوا
        if item in seen:
            rejected.append((item, "اتكرر في نفس الليستة -- اتسجل بآخر قيمة"))
        seen[item] = {
            "item": item,
            "price": price,
            "unit": " ".join(str(raw.get("unit") or "").split()),
            "note": " ".join(str(raw.get("note") or "").split()),
        }

    accepted = list(seen.values())
    overflow = max(0, len(items or []) - MAX_ITEMS)
    if overflow:
        rejected.append(
            ("(" + str(overflow) + " بند)", "زيادة عن حد الـ" + str(MAX_ITEMS) + " في النداء الواحد -- ابعتهم في ليستة تانية")
        )
    return accepted, rejected


def classify(accepted, existing):
    """يقسم البنود لـ(جديد، متغيّر، زي ما هو) بمقارنة بالموجود.

    `existing` قاموس {اسم البند: السعر الحالي}. الغرض إن التقرير يوري
    التغيير -- ده اللي بيخلي أحمد يمسك رقم غلط قبل ما يدخل مقايسة.
    """
    fresh, changed, same = [], [], []
    for entry in accepted:
        old = existing.get(entry["item"])
        if old is None:
            fresh.append(entry)
        elif str(old).strip() != entry["price"]:
            changed.append({**entry, "old_price": str(old).strip()})
        else:
            same.append(entry)
    return fresh, changed, same


def format_report(fresh, changed, same, rejected, saved_names):
    """التقرير اللي أحمد بيقراه. أرقام محسوبة، والمتغيّر متعرّض بالتفصيل."""
    saved = set(saved_names)
    lines = ["💰 سجّلت " + str(len(saved)) + " بند في قاعدة الأسعار."]

    fresh_ok = [e for e in fresh if e["item"] in saved]
    changed_ok = [e for e in changed if e["item"] in saved]
    same_ok = [e for e in same if e["item"] in saved]

    if fresh_ok:
        lines.append("")
        lines.append("● جديد (" + str(len(fresh_ok)) + "):")
        for e in fresh_ok:
            unit = (" / " + e["unit"]) if e["unit"] else ""
            lines.append("   + " + e["item"] + " = " + e["price"] + unit)

    if changed_ok:
        lines.append("")
        lines.append("● اتغيّر (" + str(len(changed_ok)) + ") -- راجعهم:")
        for e in changed_ok:
            lines.append("   ~ " + e["item"] + ": " + e["old_price"] + " ← " + e["price"])

    if same_ok:
        lines.append("")
        lines.append("● زي ما هو: " + str(len(same_ok)) + " بند")

    if rejected:
        lines.append("")
        lines.append("⚠️ متسجلش (" + str(len(rejected)) + "):")
        for name, why in rejected:
            lines.append("   - " + name + " — " + why)

    return "\n".join(lines)


def save_prices_bulk(items):
    """يسجّل ليستة أسعار مرة واحدة. بيرجع تقرير عربي جاهز للموديل."""
    accepted, rejected = validate_items(items)
    if not accepted:
        if rejected:
            return format_report([], [], [], rejected, [])
        return "مفيش بنود في الطلب -- ابعت الأسعار كـitems فيها item و price."

    from services import price_base_service as pbs

    # قراءة واحدة للقاعدة كلها قبل الحفظ -- عشان التقرير يعرف الجديد من
    # المتغيّر. أرخص من قراءة لكل بند وبيدي التقرير قيمته الحقيقية.
    existing = {}
    try:
        for doc in pbs._all_docs_supabase_first():
            name = (doc or {}).get("item")
            if name:
                existing[name] = doc.get("price")
    except Exception as e:
        logger.warning("⚠️ قراءة الأسعار الحالية فشلت -- التقرير هيقول 'جديد' على الكل: " + str(e)[:80])

    fresh, changed, same = classify(accepted, existing)

    saved_names = []
    for entry in accepted:
        try:
            result = pbs.save_price(entry["item"], entry["price"], entry["unit"], entry["note"])
            if str(result).startswith("اتسجل"):
                saved_names.append(entry["item"])
            else:
                rejected.append((entry["item"], str(result)[:70]))
        except Exception as e:
            logger.error("❌ حفظ سعر بالجملة فشل (" + entry["item"] + "): " + str(e)[:90])
            rejected.append((entry["item"], "الحفظ فشل"))

    logger.info(
        "💰 أسعار بالجملة: " + str(len(saved_names)) + " اتسجلوا، "
        + str(len(changed)) + " اتغيّروا، " + str(len(rejected)) + " اترفضوا"
    )
    return format_report(fresh, changed, same, rejected, saved_names)
