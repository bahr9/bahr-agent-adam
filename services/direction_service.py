# -*- coding: utf-8 -*-
"""
🎨 الاتجاه -- بالتة وخامات مشتقة من البريف ومعايرة بالتوقيع

ده **الطبقة اللي تحت المود بورد**: عناصر ليها أسماء وأسباب وأسعار، مش صورة.
الصورة بتتولد من العناصر دي في الآخر (`moodboard_service`)، مش العكس --
لأن الخامة المرسومة جوه بيكسلز عمرها ما توصل لسعر (تصور §5.4).

## من فين بتيجي القرارات

  1. **العميل** -- إجابات مباشرة (البالتة اللي اختارها، الفاتح ولا الغامق).
  2. **ممنوعاته** -- استبعاد. الرفض أقوى من التفضيل.
  3. **توقيع أحمد** -- المعايرة (`services/signature.py`).

وكل عنصر في المخرج شايل `why` بيقول جه من مين. نفس قاعدة `brief_reader`
والدستور: مفيش اختيار من غير أصله.

## الأسعار

بتتجاب من قاعدة أسعار أحمد بالكلمة المفتاحية. **اللي مش لاقي سعر بيتقال
صراحةً** بدل ما يتساب فاضي -- ده اللي بيقوله لأحمد إيه اللي محتاج يسعّره
قبل ما يعرض رقم.
"""

from utils.logger import logger
from services import signature as _sig


# ============================================================
# البالتات -- نفس الأربعة اللي العميل بيختار منهم في الاستمارة
# ============================================================
# النسب مقصودة: البالتة بتتعرض بنِسَبها الحقيقية في الفراغ مش قطع متساوية
# (DESIGN.md §3.4). الترتيب من السايد للمسة.

PALETTES = {
    # الأدوار مش قايمة ألوان: 60 السايد، 30 التاني الحقيقي، 10 اللمسة.
    # **الأرضية والخامات جوه النسبة مش بره** -- الباركيه اللي غطى الشقة
    # 30٪ مما العين بتشوفه، ماينفعش يتحسب لمسة.
    # اللمسة الأخيرة في كل بالتة معدن (`metal`): المعدن بيقرا **خامة مش لون**،
    # فمش بيتحسب لمسة تانية تخانق الأولى. الاختبار كشف إن البالتات كانت
    # بتكسر قاعدة "لمسة واحدة" غلط بسببه.
    "ترابي دافي": {
        "dominant": ("أوف-وايت دافي", "#EFE9DE"),
        "secondary": ("بني بلوط", "#9A7248"),
        "accents": [("أخضر غامق", "#33413A", 0.06, False), ("نحاس مطفي", "#A8834E", 0.04, True)],
    },
    "فاتح هادي": {
        "dominant": ("أبيض مكسر", "#F2EEE6"),
        "secondary": ("بيج رمادي", "#B5A692"),
        "accents": [("أخضر مغبر", "#7E8C79", 0.06, False), ("بني مطفي", "#5C5348", 0.04, False)],
    },
    "غامق فخم": {
        "dominant": ("بيج فاتح", "#D8CFC0"),
        "secondary": ("بني داكن", "#6B4F3A"),
        "accents": [("أخضر غامق", "#33413A", 0.07, False), ("دهبي مطفي", "#A6822E", 0.03, True)],
    },
    # الكحلي كان لمسة تانية قوية بتخانق الطوبي. مكانه الصح الـ30 --
    # كحلي 30 مع طوبي 10 تركيب أقوى، والقاعدة هي اللي وصّلتنا له.
    "متباين عصري": {
        "dominant": ("أوف-وايت", "#F5F2EC"),
        "secondary": ("كحلي غامق", "#29384D"),
        "accents": [("طوبي محروق", "#C25E40", 0.07, False), ("نحاس مطفي", "#A8834E", 0.03, True)],
    },
}

# قاعدة أحمد (2026-08-10): النسبة ٦٠ / ٣٠ / ١٠
DOMINANT_SHARE = 0.60
SECONDARY_SHARE = 0.30
ACCENT_SHARE = 0.10


def _rgb(hex_colour):
    h = str(hex_colour or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def check_palette(colors):
    """فحص البالتة على قواعد الطبقة التانية -- بتشتغل مع أي ألوان.

    الفحوصات دي على **بالتة الأداة نفسها** كمان، مش على العميل بس:
    قاعدة بتفحص كل حاجة إلا اللي كاتبها هي قاعدة نص.
    """
    issues = []

    # الأبيض الصافي: فاتح جدًا + فرق ضئيل بين القنوات = مفيش صبغة
    for c in colors:
        rgb = _rgb(c.get("hex"))
        if not rgb:
            continue
        r, g, b = rgb
        if min(rgb) >= 246 and (max(rgb) - min(rgb)) <= 4:
            rule = _sig.get("no_pure_white")
            issues.append({"colour": c["name"], "rule": rule["text"] if rule else "",
                           "text": "أبيض صافي — يتكسر ببيج أو رمادي دافي"})

    # البارد كمساحة كبيرة. **الشرط التشبع مش الميل للأزرق**: القاعدة عن
    # الرمادي البارد -- اللي مالوش كروما يمسك بيها نفسه تحت شمس مصر فبيروح
    # متسخ. الكحلي المشبع لون حقيقي وبيفضل كحلي.
    for c in colors:
        rgb = _rgb(c.get("hex"))
        if not rgb or c.get("share", 0) < 0.25:
            continue
        r, g, b = rgb
        greyish = (max(rgb) - min(rgb)) < 32
        if b > r + 6 and greyish:
            rule = _sig.get("no_cold_under_egyptian_sun")
            issues.append({"colour": c["name"], "rule": rule["text"] if rule else "",
                           "text": "بارد على مساحة " +
                                   str(int(round(c["share"] * 100))) + "٪ تحت شمس مصر"})

    # لمستين قويين: اللمسة "قوية" لما تبقى غامقة أو مشبعة.
    # **المعدن مستثنى** -- بيقرا خامة مش لون، ونحاس جنب أخضر مش خناقة.
    strong = []
    for c in colors:
        rgb = _rgb(c.get("hex"))
        if not rgb or c.get("role") != "لمسة" or c.get("metal"):
            continue
        r, g, b = rgb
        dark = sum(rgb) / 3 < 110
        saturated = (max(rgb) - min(rgb)) > 60
        if dark or saturated:
            strong.append(c["name"])
    if len(strong) > 1:
        rule = _sig.get("one_strong_accent")
        issues.append({"colour": "، ".join(strong), "rule": rule["text"] if rule else "",
                       "text": "لمستين قويين بيتخانقوا — واحدة تقود والتانية تهدى"})

    return issues


def check_materials(picks):
    """فحص الخامات على قواعد الطبقة التانية.

    قاعدة أحمد (2026-08-10): العاكس مساحات صغيرة أو متوسطة -- الأرضية
    العاكسة تحت السبوت بتبقى مرايا للوحدات وبتوهج العين طول اليوم.
    """
    issues = []
    by_name = {m["name"]: m for m in MATERIALS}
    for p in picks:
        m = by_name.get(p.get("name"))
        if not m or "عاكس" not in m["tags"]:
            continue
        if p.get("surface") == "أرضيات":
            rule = _sig.get("reflective_in_small_areas")
            issues.append({
                "material": p["name"],
                "rule": rule["text"] if rule else "",
                "text": "خامة عاكسة على الأرضية كلها — تحت السبوت هتبقى مرايا",
            })
    return issues


def _palette_colors(name):
    """الأدوار -> قايمة ألوان بنسبها، على 60/30/10."""
    p = PALETTES[name]
    out = [
        {"name": p["dominant"][0], "hex": p["dominant"][1],
         "share": DOMINANT_SHARE, "role": "سايد"},
        {"name": p["secondary"][0], "hex": p["secondary"][1],
         "share": SECONDARY_SHARE, "role": "تاني"},
    ]
    for n, h, s, is_metal in p["accents"]:
        out.append({"name": n, "hex": h, "share": s, "role": "لمسة", "metal": is_metal})
    return out

# ممنوعات العميل -> أي ألوان تتشال أو تخف
_BAN_FILTERS = {
    "ألوان غامقة كتير": ("غامق", "داكن", "أسود", "فحمي", "كحلي"),
    "الرمادي البارد": ("رمادي",),
    "دهبي وفضي لامع": ("دهبي",),
}


# ============================================================
# مكتبة الخامات -- صغيرة بالقصد، بتكبر لما تحتاج
# ============================================================
# كل خامة: (الاسم، السطح، مفتاح البحث في قاعدة الأسعار، الوسوم)
# الوسوم بتشتغل مع الممنوعات وقواعد التوقيع.

MATERIALS = [
    # أرضيات
    {"name": "باركيه بلوط", "surface": "أرضيات", "price_key": "باركيه",
     "tags": {"خشب", "دافي", "حساس"}, "tiers": {"متوسط", "عالي"}},
    {"name": "بورسلين 60×120", "surface": "أرضيات", "price_key": "بورسلين 60×120",
     "tags": {"حجري", "سهل التنضيف", "عاكس"}, "tiers": {"متوسط", "عالي"}},
    {"name": "بورسلين 60×60", "surface": "أرضيات", "price_key": "بورسلين 60×60",
     "tags": {"حجري", "سهل التنضيف", "اقتصادي"}, "tiers": {"اقتصادي", "متوسط"}},

    # حوائط
    {"name": "دهان مطفي", "surface": "حوائط", "price_key": "النقاش",
     "tags": {"ناعم"}, "tiers": {"اقتصادي", "متوسط", "عالي"}},
    {"name": "كلادينج خشبي", "surface": "حوائط", "price_key": "cladding wall",
     "tags": {"خشب", "خشن", "دافي"}, "tiers": {"متوسط", "عالي"}},
    {"name": "كلادينج مواصفة أخف", "surface": "حوائط", "price_key": "cladding wall مواصفة أخف",
     "tags": {"خشب", "خشن", "اقتصادي"}, "tiers": {"اقتصادي", "متوسط"}},

    # أسقف
    {"name": "جبس بورد بنزلة محيطية", "surface": "أسقف", "price_key": "الجبس بورد أبيض",
     "tags": {"ناعم"}, "tiers": {"اقتصادي", "متوسط", "عالي"}},
    {"name": "جبس بورد مقاوم للرطوبة", "surface": "أسقف", "price_key": "الجبس بورد أحمر وأخضر",
     "tags": {"ناعم", "حمامات"}, "tiers": {"اقتصادي", "متوسط", "عالي"}},

    # وحدات
    {"name": "وحدة تخزين حائطية", "surface": "وحدات", "price_key": "storage wall",
     "tags": {"خشب"}, "tiers": {"متوسط", "عالي"}},
    {"name": "قشرة مدهونة", "surface": "وحدات", "price_key": "",
     "tags": {"خشب", "ناعم"}, "tiers": {"متوسط", "عالي"}},

    # إنارة وتفاصيل
    {"name": "بروفايل ليد مخفي", "surface": "إنارة", "price_key": "بروفايل ليد",
     "tags": {"مخفي"}, "tiers": {"اقتصادي", "متوسط", "عالي"}},
    {"name": "بيت نور", "surface": "إنارة", "price_key": "بيت النور",
     "tags": {"مخفي"}, "tiers": {"متوسط", "عالي"}},
    {"name": "نحاس مطفي", "surface": "تفاصيل", "price_key": "",
     "tags": {"معدن", "دافي", "لامع"}, "tiers": {"متوسط", "عالي"},
     "offered_by": "brass_not_steel"},
    {"name": "استانلس مطفي", "surface": "تفاصيل", "price_key": "",
     "tags": {"معدن", "بارد"}, "tiers": {"اقتصادي", "متوسط", "عالي"}},
]

# ممنوعات العميل -> وسوم الخامة اللي بتتعارض معاها.
# ده اللي بيخلي اقتراح أحمد **يتنازل** قدام كلام العميل بدل ما يتفرض.
_BAN_TAGS = {
    "دهبي وفضي لامع": {"لامع"},
    "ألوان غامقة كتير": {"غامق"},
    "رفوف مفتوحة": {"مفتوح"},
}

_SURFACE_ORDER = ["أرضيات", "حوائط", "أسقف", "وحدات", "إنارة", "تفاصيل"]


# ============================================================
# أدوات
# ============================================================

def _get(answers, key):
    return (answers or {}).get(key)


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def budget_tier(answers):
    """مستوى الميزانية من الرقم -- بيحدد أي خامات واردة أصلًا."""
    raw = str(_get(answers, "الميزانية") or "")
    import re
    m = re.match(r"^([\d.]+)\s*([KM])", raw, re.IGNORECASE)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    k = n * 1000 if m.group(2).upper() == "M" else n
    if k < 400:
        return "اقتصادي"
    if k < 1200:
        return "متوسط"
    return "عالي"


# ============================================================
# البالتة
# ============================================================

def build_palette(answers):
    """بالتة بنسبها + سبب كل تعديل.

    بترجع dict فيه `colors` و`source` و`adjustments`.
    """
    chosen = _get(answers, "البالتة")
    tone = _get(answers, "فاتح ولا غامق")
    bans = _as_list(_get(answers, "ممنوعات"))

    name = chosen if chosen in PALETTES else None
    source = None
    if name:
        source = ("البالتة", chosen)
    else:
        # مفيش بالتة مختارة: نستنتج من درجة الجو
        name = "فاتح هادي" if (tone and "فاتح" in str(tone)) else "ترابي دافي"
        source = ("فاتح ولا غامق", tone) if tone else None

    colors = _palette_colors(name)

    adjustments = []
    for ban in bans:
        words = _BAN_FILTERS.get(ban)
        if not words:
            continue
        hit = [c for c in colors if any(w in c["name"] for w in words)]
        if not hit:
            continue
        # اللون الممنوع بيتقلّص لنص نصيبه، والفرق بيروح للسايد --
        # الشيل الكامل بيكسر البالتة، والتقليص بيحترم الرفض من غير ما يفقّرها
        freed = 0.0
        for c in hit:
            freed += c["share"] / 2
            c["share"] = round(c["share"] / 2, 3)
            c["muted"] = True
        colors[0]["share"] = round(colors[0]["share"] + freed, 3)
        adjustments.append({
            "ban": ban,
            "affected": [c["name"] for c in hit],
            "why": "ممنوع عند العميل، فنصيبه اتقلّص والباقي راح للسايد",
        })

    # اللمسة اللي خفّت عن ٥٪ بقت خجولة -- والخجل في اللمسة بيسطّح الفراغ
    accent_total = round(sum(c["share"] for c in colors if c["role"] == "لمسة"), 3)
    timid = accent_total < 0.05

    return {
        "name": name, "colors": colors, "source": source, "adjustments": adjustments,
        "accent_total": accent_total, "timid_accent": timid,
        "issues": check_palette(colors),
        "rule": _sig.get("palette_60_30_10"),
    }


# ============================================================
# الخامات
# ============================================================

def _price_for(key, price_lookup):
    if not key or not price_lookup:
        return None
    return price_lookup(key)


def build_materials(answers, price_lookup=None):
    """خامة لكل سطح، مع سببها وسعرها لو موجود.

    `price_lookup` دالة بتاخد كلمة مفتاحية وترجع نص السعر أو None --
    متحقونة عشان الاختبارات تفضل من غير شبكة.
    """
    tier = budget_tier(answers)
    bans = set(_as_list(_get(answers, "ممنوعات")))
    kitchen = str(_get(answers, "المطبخ مفتوح") or "")
    cleaning = str(_get(answers, "النضافة") or "")
    pets = str(_get(answers, "حيوانات") or "")
    kids = str(_get(answers, "أطفال") or "")

    heavy_use = ("أيوه" in kids) or (pets and pets != "لأ")

    # ممنوعات العميل -> وسوم مرفوضة. دي **أقوى من اقتراحات أحمد** بالتصميم.
    banned_tags = set()
    ban_reason = {}
    for b in bans:
        for t in _BAN_TAGS.get(b, ()):
            banned_tags.add(t)
            ban_reason[t] = b

    picks = []
    yielded = []          # اقتراحات أحمد اللي اتنازلت -- بتتقال بصوت عالي
    used_wood = 0

    for surface in _SURFACE_ORDER:
        options = [m for m in MATERIALS if m["surface"] == surface]
        if tier:
            fit = [m for m in options if tier in m["tiers"]]
            if fit:
                options = fit
        if not options:
            continue

        # الخامة اللي بتخالف ممنوع العميل بتتشال، ولو كانت اقتراح أحمد
        # التنازل بيتسجّل بدل ما يعدي في صمت
        allowed = []
        for m in options:
            clash = m["tags"] & banned_tags
            if clash:
                if m.get("offered_by"):
                    rule = _sig.get(m["offered_by"])
                    yielded.append({
                        "material": m["name"],
                        "rule": rule["text"] if rule else m["offered_by"],
                        "ban": ban_reason[sorted(clash)[0]],
                    })
                continue
            allowed.append(m)
        if allowed:
            options = allowed

        chosen, why = None, []

        for m in options:
            # قاعدة التوقيع: حد الأخشاب في الفراغ الواحد
            if "خشب" in m["tags"] and used_wood >= 2:
                continue
            chosen = m
            break
        if chosen is None:
            chosen = options[0]

        if tier:
            why.append({"source": "الميزانية", "text": "مستوى " + tier})
        if "خشب" in chosen["tags"]:
            used_wood += 1

        # قواعد التوقيع اللي بتنطبق على الاختيار ده.
        # "خشن جنب ناعم" **مش هنا**: دي قاعدة تركيب على المجموعة كلها،
        # وتكرارها على كل عنصر بيخليها ضوضاء بدل ما تبقى ملاحظة.
        rules = []
        if chosen.get("offered_by"):
            r = _sig.get(chosen["offered_by"])
            if r:
                rules.append(r)
        if "مخفي" in chosen["tags"]:
            r = _sig.get("hidden_source")
            if r:
                rules.append(r)
        if surface == "أرضيات":
            r = _sig.get("one_continuous_floor")
            if r:
                rules.append(r)
        # الطبقة بتحدد النبرة: الطريقة قاعدة، والذوق اقتراح
        for r in rules:
            why.append({
                "source": "اقتراحك" if r.get("layer") == _sig.OFFER else "طريقتك",
                "text": r["text"],
            })

        warnings = []
        # التحذير للخامة الحساسة بس -- تحذير على كل حاجة بيتساب بعد يومين
        if heavy_use and "حساس" in chosen["tags"]:
            r = _sig.get("maintenance_before_beauty")
            warnings.append({
                "text": "استعمال يومي تقيل (" +
                        ("عيال" if "أيوه" in kids else "حيوانات") + ") مع " + chosen["name"],
                "rule": r["text"] if r else None,
                "basis": [("النضافة", cleaning)] if cleaning else [],
            })

        picks.append({
            "surface": surface,
            "name": chosen["name"],
            "why": why,
            "warnings": warnings,
            "price": _price_for(chosen["price_key"], price_lookup),
            "price_key": chosen["price_key"],
        })

    # المطبخ المقفول محتاج سقف مقاوم رطوبة كمان -- ملاحظة مش اختيار
    if "مقفول" in kitchen:
        for p in picks:
            if p["surface"] == "أسقف":
                p["note"] = "المطبخ والحمامات محتاجين جبس مقاوم للرطوبة"

    return picks, yielded


def composition_notes(picks):
    """قواعد التوقيع اللي بتتحقق على المجموعة كلها مش على عنصر لوحده.

    "خشن جنب ناعم" كانت بتتكرر على كل خامة فبقت ضوضاء. الصح إنها تتقال
    مرة واحدة، ولما تبقى مكسورة بس.
    """
    tags = set()
    for p in picks:
        for m in MATERIALS:
            if m["name"] == p["name"]:
                tags |= m["tags"]

    notes = []
    rule = _sig.get("rough_beside_smooth")
    if rule and not ("خشن" in tags and "ناعم" in tags):
        notes.append({
            "rule": rule["text"],
            "text": "المجموعة كلها " + ("ناعمة" if "ناعم" in tags else "خشنة") +
                    " — ناقصها تباين ملمسي.",
        })
    return notes


# ============================================================
# التجميع والعرض
# ============================================================

def build_direction(row, price_lookup=None):
    answers = (row or {}).get("answers") or {}
    materials, yielded = build_materials(answers, price_lookup)
    return {
        "palette": build_palette(answers),
        "materials": materials,
        "yielded": yielded,
        "composition": composition_notes(materials),
        "material_issues": check_materials(materials),
        "tier": budget_tier(answers),
    }


def _bar(share):
    """شريط نصي للنسبة -- تليجرام مفيهوش ألوان، فالنسبة لازم تتشاف."""
    n = max(1, int(round(share * 20)))
    return "█" * n


def format_direction(row, direction=None, price_lookup=None):
    direction = direction or build_direction(row, price_lookup)
    answers = (row or {}).get("answers") or {}
    name = (row or {}).get("client_name") or answers.get("الاسم") or "من غير اسم"

    pal = direction["palette"]
    out = ["🎨 اتجاه مقترح — " + name]
    if direction["tier"]:
        out.append("مستوى: " + direction["tier"])

    out.append("\n🎯 البالتة — " + pal["name"] + "  (٦٠ / ٣٠ / ١٠)")
    if pal["source"]:
        out.append("↳ من " + pal["source"][0] + ": " + str(pal["source"][1]))
    for c in pal["colors"]:
        pct = str(int(round(c["share"] * 100))) + "٪"
        line = "• " + _bar(c["share"]) + " " + c["name"] + " " + pct + " · " + c["role"]
        if c.get("muted"):
            line += " (اتقلّص)"
        out.append(line)
    for a in pal["adjustments"]:
        out.append("⚠️ «" + a["ban"] + "» — " + "، ".join(a["affected"]) + ": " + a["why"])
    for iss in pal.get("issues", []):
        out.append("⚠️ " + iss["colour"] + " — " + iss["text"])
        if iss.get("rule"):
            out.append("   طريقتك: «" + iss["rule"] + "»")
    if pal.get("timid_accent"):
        out.append("⚠️ اللمسة نزلت لـ " + str(int(round(pal["accent_total"] * 100))) +
                   "٪ بعد الممنوعات — خجولة كده والفراغ هيقرا مسطح. "
                   "يا تلتزم بيها يا تشيلها خالص.")

    out.append("\n🧱 الخامات:")
    missing = []
    for m in direction["materials"]:
        head = "• " + m["surface"] + ": " + m["name"]
        if m["price"]:
            head += " — " + m["price"]
        else:
            head += " — مش في قاعدة أسعارك"
            missing.append(m["name"])
        out.append(head)
        for w in m["why"]:
            out.append("   ↳ " + w["source"] + ": " + w["text"])
        for warn in m["warnings"]:
            out.append("   ⚠️ " + warn["text"])
            if warn.get("rule"):
                out.append("      قاعدتك: «" + warn["rule"] + "»")
        if m.get("note"):
            out.append("   ℹ️ " + m["note"])

    # التنازل بيتقال بصوت عالي: أحمد يقدر يتدخل عن قصد بدل ما يكتشف بعدين
    for y in direction.get("yielded", []):
        out.append("\n🤝 نزلت عن «" + y["material"] + "»")
        out.append("   اقتراحك: «" + y["rule"] + "»")
        out.append("   العميل منع: " + y["ban"])

    for iss in direction.get("material_issues", []):
        out.append("\n⚠️ " + iss["material"] + " — " + iss["text"])
        out.append("   طريقتك: «" + iss["rule"] + "»")

    for note in direction.get("composition", []):
        out.append("\n🧩 " + note["text"])
        out.append("   طريقتك: «" + note["rule"] + "»")

    if missing:
        out.append("\n❔ محتاج تسعّرها قبل ما تعرض رقم: " + "، ".join(missing))

    return "\n".join(out)
