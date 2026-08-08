# -*- coding: utf-8 -*-
"""
📐➜💰 المقايسة -- الحلقة اللي كانت ناقصة بين البلان والسعر.

قبل الملف ده كانت السلسلة بتقف في النص:

    بلان -> ملف مشروع (فراغات + أبعاد + مساحات محسوبة) -> ??? -> مفيش
                                                          ^
                                                 قاعدة الأسعار

آدم كان يقدر يقول "الريسبشن 6.00 × 4.50" ويقدر يقول "متر البورسلين 526"،
ومش قادر يقول الريسبشن هيكلّف كام. المقايسة هي ناتج المرحلة المعمارية في
شغل أحمد، فالحلقة دي هي اللي بتحوّل كل اللي فات لحاجة تتسلّم لعميل.

## القاعدة الحاكمة: المكتوب بس

المساحة بتتحسب حتميًا من الأبعاد **المكتوبة في البلان** (`computed_area`
الموجودة أصلًا في `project_file_service` -- ضرب بايثون، مش تقدير). فراغ
مالوش أبعاد مكتوبة **مبيتحسبش ومبيتقدّرش** -- بيتقال اسمه في التحذير.

نفس القاعدة على الأسعار: بند مش في قاعدة أحمد **بيتقال بالاسم** بدل ما
يتخطى بصمت. الرقم الناقص اللي حد واخد باله منه أأمن بكتير من رقم كامل
نصه مخترع.

## المصنعية والخامة منفصلين

قرار أحمد (2026-08-08): "خلي المصنعية لوحدها والخامة لوحدها لأني بفصلهم
فعليًا". فمفيش ربط ولا جمع تلقائي بينهم -- كل بند سطر مستقل بسعره، زي
ما بيتعامل بيهم في السوق فعلًا. الملف ده مش بيفترض إن كل خامة ليها
مصنعية ولا العكس.

## الحوائط مش محسوبة

الأرضيات والأسقف = مساحة الفراغ. الحوائط = المحيط × الارتفاع، **والارتفاع
مبيتكتبش في البلان** -- فبند الحوائط لازم يتبعت بكمية صريحة (`manual`)
أو ميتحسبش. ده مش نقص في الأداة، ده حدود المصدر.
"""

from utils.logger import logger

# أساس الكمية لكل بند
BASIS_FLOOR = "floor"       # مساحة الأرضيات = مجموع مساحات الفراغات
BASIS_CEILING = "ceiling"   # مساحة الأسقف = نفس المساحة (سقف مسطح)
BASIS_MANUAL = "manual"     # كمية صريحة من أحمد (محيط، متر طولي، قطع)
_AREA_BASES = (BASIS_FLOOR, BASIS_CEILING)

MAX_LINES = 40


# ============================================================
# منطق pure -- قابل للاختبار من غير Firestore ولا شبكة
# ============================================================

def measured_rooms(doc):
    """الفراغات اللي ليها مساحة محسوبة فعلًا.

    بيرجع (measured, unmeasured):
      measured   -> [(اسم, مساحة)]  من فئة "أبعاد" اللي فيها computed_area_m2
      unmeasured -> [اسم]           فراغات من غير مساحة -- بتتقال بالاسم

    `computed_area_m2` بيتكتب في `save_project_fact` من الأبعاد المكتوبة
    بس. غيابه معناه "مش معروف" مش "صفر" -- وعشان كده الفراغ بيدخل قايمة
    الناقص بدل ما يتحسب بصفر ويختفي من التحذير.
    """
    facts = (doc or {}).get("facts") or {}
    measured, unmeasured = [], []

    for name, entry in sorted((facts.get("أبعاد") or {}).items()):
        area = entry.get("computed_area_m2") if isinstance(entry, dict) else None
        if isinstance(area, (int, float)) and area > 0:
            measured.append((name, float(area)))
        else:
            unmeasured.append(name)

    # فئة "فراغات" هي بالتعريف اللي مالوش أبعاد (بيكتبها plan_capture كده)
    unmeasured.extend(sorted((facts.get("فراغات") or {}).keys()))
    return measured, unmeasured


def boxes_needed(area, coverage):
    """عدد الصناديق الكاملة اللي تغطي المساحة، أو None لو التغطية مش معروفة.

    البلاط بيتباع صناديق مش أمتار (ماحجوب: 60×120 -> 1.44 م² للصندوق)،
    فأرضية 100 متر عايزة 70 صندوق = 100.8 متر. الفرق بيتراكم في مشروع
    كبير وبيبان وقت التنفيذ لما الكمية متكفّيش.

    التغطية **مبتتخمنش من اسم البند**: مقاس البلاطة مش هو محتوى الصندوق،
    والمصانع بتختلف. من غير رقم مسجّل بترجع None والكمية بتفضل بالمتر.
    """
    if not coverage or coverage <= 0 or not area or area <= 0:
        return None
    import math
    return math.ceil(area / float(coverage))


def _price_range(entry):
    """(من، إلى) بالأرقام من سجل السعر، أو (None, None) لو مش مفهوم."""
    if not entry:
        return None, None
    for lo_key, hi_key in (("price_min", "price_max"), ("min", "max")):
        lo, hi = entry.get(lo_key), entry.get(hi_key)
        if isinstance(lo, (int, float)):
            return float(lo), (float(hi) if isinstance(hi, (int, float)) else None)
    try:
        from migration_transform import parse_price_range
        return parse_price_range(entry.get("price"), "estimate")
    except Exception:
        return None, None


def build_line(spec, area, price_entry):
    """سطر مقايسة واحد. بيرجع dict فيه الكمية والتكلفة أو سبب التعذر."""
    item = spec.get("item")
    basis = spec.get("basis") or BASIS_FLOOR

    if basis == BASIS_MANUAL:
        qty = spec.get("quantity")
        if not isinstance(qty, (int, float)) or qty <= 0:
            return {"item": item, "skipped": "كمية يدوية ناقصة أو مش رقم"}
        quantity, unit = float(qty), (spec.get("unit") or "")
    elif basis in _AREA_BASES:
        if not area:
            return {"item": item, "skipped": "مفيش مساحة محسوبة في ملف المشروع"}
        quantity, unit = float(area), "م²"
    else:
        return {"item": item, "skipped": "أساس كمية مش معروف: " + str(basis)}

    if price_entry is None:
        return {"item": item, "quantity": quantity, "unit": unit,
                "skipped": "السعر مش في قاعدة أسعارك"}

    low, high = _price_range(price_entry)
    if low is None:
        return {"item": item, "quantity": quantity, "unit": unit,
                "skipped": "السعر المسجّل مش مفهوم كرقم"}

    boxes = boxes_needed(quantity, price_entry.get("box_coverage_m2")) if basis in _AREA_BASES else None
    billed = quantity
    if boxes is not None:
        # الشرا بالصندوق: الفلوس بتتحسب على اللي هيتشترى فعلًا مش اللي هيتركب
        billed = boxes * float(price_entry["box_coverage_m2"])

    return {
        "item": item, "basis": basis, "quantity": quantity, "unit": unit,
        "boxes": boxes, "billed_quantity": billed,
        "unit_price_low": low, "unit_price_high": high,
        "cost_low": billed * low,
        "cost_high": (billed * high) if high is not None else None,
        "price_unit": price_entry.get("unit") or "",
    }


def _fmt(number):
    if number is None:
        return "؟"
    return "{:,.0f}".format(float(number)) if float(number) >= 100 else "{:,.2f}".format(float(number)).rstrip("0").rstrip(".")


def format_estimate(project_name, measured, unmeasured, lines):
    """نص المقايسة. التحذير **قبل** أي رقم، مش بعده.

    السبب مش تنسيقي: رقم جزئي متقري قبل التحذير بيدخل دماغ اللي بيقراه
    كإجمالي، والتحذير بعده بيتحول لتفصيلة. نفس القاعدة الموجودة في برومبت
    آدم للتكلفة الجزئية.
    """
    total_area = sum(a for _, a in measured)
    out = []

    if unmeasured:
        out.append(
            "⚠️ **تقدير جزئي** -- محسوب على " + str(len(measured)) + " فراغ من "
            + str(len(measured) + len(unmeasured)) + ". "
            + "مش داخل فيه: " + "، ".join(unmeasured[:8])
            + (" وغيرهم" if len(unmeasured) > 8 else "")
            + " (مالهمش أبعاد مكتوبة)."
        )
        out.append("")

    out.append("📐 **مقايسة " + str(project_name) + "**")
    if measured:
        out.append("المساحة المحسوبة: " + _fmt(total_area) + " م² — "
                   + "، ".join(n + " " + _fmt(a) for n, a in measured))
    else:
        # كان بيطلع "المساحة المحسوبة: 0 م² — " بشرطة ومفيش حاجة وراها.
        # صفر متر مش مساحة، ده غياب مساحة -- والفرق بين الاتنين هو نفس
        # القاعدة اللي في كل حتة: مش عارف ≠ صفر (اتكشف في أول تشغيلة
        # حقيقية على ملف Rock Eden، 2026-08-08).
        out.append("مفيش ولا فراغ ليه أبعاد مكتوبة في الملف ده.")
    out.append("")

    priced = [l for l in lines if "cost_low" in l]
    skipped = [l for l in lines if "skipped" in l]

    if priced:
        for l in priced:
            qty = _fmt(l["quantity"]) + " " + l["unit"]
            if l.get("boxes"):
                qty += " → **" + str(l["boxes"]) + " صندوق** (" + _fmt(l["billed_quantity"]) + " م² مشتراة)"
            cost = _fmt(l["cost_low"]) + (" — " + _fmt(l["cost_high"]) if l.get("cost_high") else "")
            out.append("• " + l["item"])
            out.append("   " + qty + " × " + _fmt(l["unit_price_low"])
                       + (":" + _fmt(l["unit_price_high"]) if l.get("unit_price_high") else "")
                       + "  =  **" + cost + " ج.م**")

        low = sum(l["cost_low"] for l in priced)
        high = sum((l["cost_high"] or l["cost_low"]) for l in priced)
        out.append("")
        out.append("**الإجمالي للبنود المحسوبة: " + _fmt(low)
                   + (" — " + _fmt(high) if high != low else "") + " ج.م**")

    if skipped:
        out.append("")
        out.append("❌ **مش محسوب (" + str(len(skipped)) + "):**")
        for l in skipped:
            out.append("   - " + str(l["item"]) + " — " + l["skipped"])
        if any("قاعدة أسعارك" in l["skipped"] for l in skipped):
            out.append("سجّل الأسعار الناقصة بـsave_prices_bulk والمقايسة هتكمل لوحدها.")

    if not priced:
        # الخطوة الجاية بتتحدد من **سبب** التعذر الغالب مش من كونه تعذّر.
        # الرسالة كانت بتقول "محتاجة أسعار" حتى لما السبب أبعاد ناقصة --
        # يعني بتبعت أحمد يسجّل أسعار وهي مش هتحل حاجة (2026-08-08).
        out.append("")
        if not measured:
            out.append("مفيش ولا بند اتحسب — الناقص **أبعاد** مش أسعار. "
                       "ابعت بلان المشروع وأنا أمسك منه الفراغات وأبعادها، "
                       "أو قوللي أبعاد كل فراغ وأسجّلها.")
        else:
            out.append("مفيش ولا بند اتحسب — المقايسة محتاجة أسعار مسجّلة الأول.")

    return "\n".join(out)


# ============================================================
# التجميع (قراءة بس -- صفر كتابة)
# ============================================================

def estimate_project_cost(project_name, lines=None):
    """مقايسة مشروع من ملفه وقاعدة الأسعار. قراءة بس."""
    from services import project_file_service as pfs

    name = " ".join(str(project_name or "").split())
    if not name:
        return "قوللي اسم المشروع."

    names = pfs.list_project_names()
    status, matches = pfs.resolve_project_name(name, names)
    if status == "ambiguous":
        return "فيه أكتر من مشروع بالاسم ده: " + "، ".join(matches) + " -- أنهي واحد؟"
    if status == "none":
        return ("مفيش ملف مشروع بالاسم ده."
                + (" الموجود: " + "، ".join(sorted(names)) if names else " مفيش ملفات مشاريع لسه."))

    resolved = matches[0]
    from services.project_file_service import _collection, project_id_for_name
    snapshot = _collection().document(project_id_for_name(resolved)).get()
    doc = snapshot.to_dict() if snapshot.exists else {}

    measured, unmeasured = measured_rooms(doc)
    if not measured and not unmeasured:
        return ("ملف مشروع " + resolved + " مفيهوش فراغات مسجّلة لسه. "
                "ابعت البلان وأنا أمسكه، أو قوللي الأبعاد.")

    total_area = sum(a for _, a in measured)

    specs = list(lines or [])[:MAX_LINES]
    if not specs:
        return (format_estimate(resolved, measured, unmeasured, [])
                + "\n\nقوللي البنود اللي عايزها في المقايسة (خامات ومصنعيات) وأنا أحسبها.")

    # قراءة واحدة لقاعدة الأسعار كلها بدل قراءة لكل بند
    from services import price_base_service as pbs

    by_item = {}
    try:
        for d in pbs._all_docs_supabase_first():
            if (d or {}).get("item"):
                by_item[d["item"]] = d
    except Exception as e:
        logger.warning("⚠️ قراءة الأسعار للمقايسة فشلت: " + str(e)[:80])

    built = []
    for spec in specs:
        wanted = str(spec.get("item") or "").strip()
        entry = by_item.get(wanted)
        if entry is None and wanted:
            # تطابق جزئي وحيد بس. أكتر من مرشح = التباس، والتباس في سعر
            # داخل مقايسة عميل أخطر من بند ناقص -- فبيترفض ويتقال.
            hits = pbs.search_items(wanted, list(by_item))
            entry = by_item[hits[0]] if len(hits) == 1 else None
        built.append(build_line(spec, total_area, entry))

    logger.info("📐 مقايسة " + resolved + ": " + str(len(built)) + " بند، "
                + _fmt(total_area) + " م²")
    return format_estimate(resolved, measured, unmeasured, built)
