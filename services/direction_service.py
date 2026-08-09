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
    "ترابي دافي": [
        ("أوف-وايت دافي", "#EFE9DE", 0.45),
        ("بيج رملي", "#DCCBB4", 0.25),
        ("بني بلوط", "#9A7248", 0.18),
        ("أخضر غامق", "#33413A", 0.08),
        ("نحاس مطفي", "#A8834E", 0.04),
    ],
    "فاتح هادي": [
        ("أبيض مكسر", "#F2EEE6", 0.48),
        ("رمادي دافي", "#E3DCD0", 0.24),
        ("بيج رمادي", "#B5A692", 0.16),
        ("أخضر مغبر", "#7E8C79", 0.08),
        ("بني مطفي", "#5C5348", 0.04),
    ],
    "غامق فخم": [
        ("بيج فاتح", "#D8CFC0", 0.38),
        ("بني داكن", "#6B4F3A", 0.24),
        ("أخضر غامق", "#33413A", 0.22),
        ("أسود مخضر", "#1F2422", 0.11),
        ("دهبي مطفي", "#A6822E", 0.05),
    ],
    "متباين عصري": [
        ("أوف-وايت", "#F5F2EC", 0.44),
        ("بيج ذهبي", "#D9C7A7", 0.22),
        ("طوبي محروق", "#C25E40", 0.16),
        ("كحلي غامق", "#29384D", 0.13),
        ("فحمي", "#2B2B2B", 0.05),
    ],
}

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
     "tags": {"حجري", "سهل التنضيف"}, "tiers": {"متوسط", "عالي"}},
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
     "tags": {"معدن", "دافي"}, "tiers": {"متوسط", "عالي"}},
]

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

    colors = [{"name": n, "hex": h, "share": s} for n, h, s in PALETTES[name]]

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

    return {"name": name, "colors": colors, "source": source, "adjustments": adjustments}


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

    picks = []
    used_wood = 0

    for surface in _SURFACE_ORDER:
        options = [m for m in MATERIALS if m["surface"] == surface]
        if tier:
            fit = [m for m in options if tier in m["tiers"]]
            if fit:
                options = fit
        if not options:
            continue

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
        if "معدن" in chosen["tags"]:
            r = _sig.get("brass_not_steel")
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
        for r in rules:
            why.append({"source": "توقيعك", "text": r["text"]})

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

    return picks


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
    materials = build_materials(answers, price_lookup)
    return {
        "palette": build_palette(answers),
        "materials": materials,
        "composition": composition_notes(materials),
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

    out.append("\n🎯 البالتة — " + pal["name"])
    if pal["source"]:
        out.append("↳ من " + pal["source"][0] + ": " + str(pal["source"][1]))
    for c in pal["colors"]:
        pct = str(int(round(c["share"] * 100))) + "٪"
        line = "• " + _bar(c["share"]) + " " + c["name"] + " " + pct
        if c.get("muted"):
            line += " (اتقلّص)"
        out.append(line)
    for a in pal["adjustments"]:
        out.append("⚠️ «" + a["ban"] + "» — " + "، ".join(a["affected"]) + ": " + a["why"])

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

    for note in direction.get("composition", []):
        out.append("\n🧩 " + note["text"])
        out.append("   قاعدتك: «" + note["rule"] + "»")

    if missing:
        out.append("\n❔ محتاج تسعّرها قبل ما تعرض رقم: " + "، ".join(missing))

    return "\n".join(out)
