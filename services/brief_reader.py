# -*- coding: utf-8 -*-
"""
🔍 قراءة البريف -- تحويل إجابات الاستبيان لقراءة تصميمية

الفكرة اللي المحرك ده مبني عليها: القراءة المهنية للبريف مش اجتهاد،
دي **تراكيب إجابات**. "الميزانية شاملة كل حاجة + دوبلكس على الطوب" تركيب،
و"السترة مهمة + عزومة 7-12 + أربع عيال" تركيب. فالقواعد أدق من تخمين
موديل، وبتتختبر، وببلاش.

## الالتزام بالدستور (CONSTITUTION.md §0)

تعريف الـ Claim بيشمل **External-entity claims**: أي جملة بتسند حالة أو نية
لكيان تالت (العميل) كواقع محتاجة دليل أو صياغة استفهامية.

فالمخرج هنا **مفصول لتلات أنواع بالقصد**:
  - `facts`   -- نقل حرفي لإجابة العميل. دليل، مش ادعاء.
  - `flags`   -- استنتاج، **وكل واحد شايل `basis`** (الإجابات اللي ولّدته).
  - `questions` -- أسئلة حقيقية للمعاينة. السؤال الصادق مش ادعاء (§0).

وممنوع في كل النصوص هنا صيغة "العميل عايز/حاسس/مش مرتاح". الصيغة المسموحة:
"اختار"، "كتب"، "قال" (حقيقة)، أو سؤال صريح.

**نطاق الإنفاذ:** الدستور موثّق إن الإنفاذ الآلي (Claim Validator) لسه مبني
لنطاق الأقساط بس، وإن external-entity claims فجوة موثقة مش خطأ مخفي. يعني
الالتزام هنا **بالتصميم مش بالفاليديتور** -- محفور في بنية المخرج نفسها:
مفيش حقل حر يسمح بادعاء بلا basis.
"""

import re

from utils.logger import logger


# ============================================================
# أدوات قراءة الإجابات
# ============================================================

def _get(answers, key):
    return (answers or {}).get(key)


def _has(v):
    return v not in (None, "", []) and not (isinstance(v, list) and not v)


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _contains(answers, key, needle):
    """الإجابة (نص أو قايمة) فيها الكلمة دي؟"""
    v = _get(answers, key)
    if not _has(v):
        return False
    return any(needle in str(x) for x in _as_list(v))


def budget_thousands(answers):
    """'500K' -> 500 · '1.25M' -> 1250 · '3M+' -> 3000 · مش موجود -> None"""
    raw = _get(answers, "الميزانية")
    if not _has(raw):
        return None
    text = str(raw).strip()
    m = re.match(r"^([\d.]+)\s*([KM])", text, re.IGNORECASE)
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    return int(num * 1000) if m.group(2).upper() == "M" else int(num)


def guests_count(answers):
    """أكبر عدد ضيوف كرقم تقريبي للمقارنة."""
    v = _get(answers, "عدد العزومة")
    if not _has(v):
        return None
    text = str(v)
    if "أكتر" in text:
        return 13
    if "٧" in text or "7" in text:
        return 12
    return 6


# ============================================================
# القواعد
# ============================================================
# كل قاعدة: (id, دالة بترجع None أو dict فيه title/basis/question)
# الـ basis إجباري في كل flag -- ده اللي بيمنع الادعاء بلا دليل.

_BIG_UNITS = ("دوبلكس", "فيلا")
_LIGHT_PALETTES = ("فاتح هادي", "متباين عصري")

# توقيع أحمد عاش في `services/signature.py` (السجل الكامل).
# الفرق مقصود ومحفور في المخرج (`source`): قاعدة البريف بتتغير مع كل عميل،
# وقاعدة التوقيع بتتطبق على كل مشروع.
from services import signature as _sig


def _r_budget_scope(a):
    b = budget_thousands(a)
    unit = _get(a, "نوع الوحدة")
    scope = _get(a, "شمول الميزانية")
    service = _get(a, "الخدمة")
    if b is None or not _has(unit) or not _has(scope):
        return None
    big = any(u in str(unit) for u in _BIG_UNITS)
    everything = "كل حاجة" in str(scope)
    # وحدة كبيرة + شامل كل حاجة + رقم أقل من 2 مليون = مشدود
    if big and everything and b < 2000:
        basis = [("نوع الوحدة", unit), ("شمول الميزانية", scope), ("الميزانية", _get(a, "الميزانية"))]
        if _has(service):
            basis.append(("الخدمة", service))
        return {
            "severity": "high",
            "title": "الميزانية والنطاق محتاجين يتقاسوا على مساحة حقيقية",
            "detail": "الرقم شامل التشطيب والفرش والأجهزة لوحدة كبيرة. لازم يتحول لسعر متر قبل أي وعد.",
            "basis": basis,
            "question": "الوحدة كام متر بالظبط؟ (عشان نحول الميزانية لسعر متر)",
        }
    return None


def _r_privacy_vs_guests(a):
    g = guests_count(a)
    privacy = _get(a, "السترة")
    if g is None or not _has(privacy) or "أيوه" not in str(privacy):
        return None
    if g < 7:
        return None
    basis = [("السترة", privacy), ("عدد العزومة", _get(a, "عدد العزومة"))]
    kids = _get(a, "أطفال")
    if _has(kids) and "أيوه" in str(kids):
        basis.append(("أطفال", kids))
    return {
        "severity": "high",
        "title": "السترة مع العزومات = مسألة حركة مش شكل",
        "detail": "مسار الضيوف ومسار البيت لازم ينفصلوا في التوزيع، ومش بيتحل بعدين.",
        "basis": basis,
        "question": None,
    }


def _r_ramadan_peak(a):
    ram = _get(a, "عزومات رمضان")
    g = guests_count(a)
    if not _has(ram) or "أكيد" not in str(ram):
        return None
    if g is None or g < 7:
        return None
    return {
        "severity": "medium",
        "title": "الذروة رمضان مش اليوم العادي",
        "detail": "التصميم اللي شايل العدد العادي بيقع في العزومة الكبيرة. القياس يبقى على الذروة.",
        "basis": [("عزومات رمضان", ram), ("عدد العزومة", _get(a, "عدد العزومة"))],
        "question": "أكبر عزومة رمضان بتوصل كام فرد؟",
    }


def _r_girl_among_boys(a):
    kids = _get(a, "أطفال")
    details = _get(a, "تفاصيل الأطفال")
    if not _has(kids) or "أيوه" not in str(kids) or not _has(details):
        return None
    text = str(details)
    has_girl = ("بنت" in text) or ("بنات" in text)
    has_boy = ("ولد" in text) or ("اولاد" in text) or ("أولاد" in text)
    if not (has_girl and has_boy):
        return None
    bunk = _contains(a, "احتياج أوضة الأطفال", "سرير دورين")
    rule = _sig.get("separate_genders")
    # قاعدة مقترحة بتتعرض كسؤال مش كحكم (الدستور §0)
    if not rule or rule["status"] != _sig.CONFIRMED:
        return None
    detail = "الفصل بيغير عدد الأوض المطلوبة، فبيتحدد في التوزيع من أول يوم."
    if bunk:
        detail = ("طلب سرير الدورين معناه مشاركة أوضة، وده بيصطدم بقاعدتك. "
                  "الفصل بيغير عدد الأوض المطلوبة من أول يوم.")
    return {
        "severity": "high",
        "source": "توقيعك",
        "rule": rule["text"],
        "title": "فيه أولاد وبنات — قاعدة الفصل بتتطبق هنا",
        "detail": detail,
        "basis": [("تفاصيل الأطفال", details)] +
                 ([("احتياج أوضة الأطفال", _get(a, "احتياج أوضة الأطفال"))] if bunk else []),
        "question": "الأعمار الحالية إيه بالظبط، ومين هينام مع مين؟",
    }


def _r_light_palette_load(a):
    pal = _get(a, "البالتة")
    tone = _get(a, "فاتح ولا غامق")
    light = (_has(pal) and str(pal) in _LIGHT_PALETTES) or \
            (_has(tone) and "فاتح" in str(tone))
    if not light:
        return None
    pets = _get(a, "حيوانات")
    kids = _get(a, "أطفال")
    has_pets = _has(pets) and str(pets) not in ("لأ",)
    has_kids = _has(kids) and "أيوه" in str(kids)
    if not (has_pets or has_kids):
        return None
    basis = []
    if _has(pal):
        basis.append(("البالتة", pal))
    elif _has(tone):
        basis.append(("فاتح ولا غامق", tone))
    if has_pets:
        basis.append(("حيوانات", pets))
    if has_kids:
        basis.append(("أطفال", kids))
    clean = _get(a, "النضافة")
    if _has(clean):
        basis.append(("النضافة", clean))
    return {
        "severity": "medium",
        "title": "بالتة فاتحة مع حمل استعمال يومي",
        "detail": "الأقمشة والتشطيبات لازم تتختار على معيار التنضيف مش الشكل. يتقال قبل اختيار المقاعد.",
        "basis": basis,
        "question": None,
    }


def _r_kitchen_contradiction(a):
    smell = _get(a, "ريحة الأكل")
    kitchen = _get(a, "المطبخ مفتوح")
    if not _has(smell) or not _has(kitchen):
        return None
    if "تتحبس" in str(smell) and "مفتوح" in str(kitchen):
        return {
            "severity": "high",
            "title": "إجابتين متعارضتين في المطبخ",
            "detail": "طلب حبس الريحة مع مطبخ مفتوح. لازم يتحسم في المعاينة بحل وسط (زجاج منزلق / شفاط قوي) أو اختيار واحد.",
            "basis": [("ريحة الأكل", smell), ("المطبخ مفتوح", kitchen)],
            "question": "المطبخ المفتوح أهم ولا حبس الريحة أهم؟",
        }
    return None


def _r_closed_kitchen_appliances(a):
    kitchen = _get(a, "المطبخ مفتوح")
    apps = _as_list(_get(a, "أجهزة المطبخ"))
    washer = _get(a, "مكان الغسالة")
    if not _has(kitchen) or "مقفول" not in str(kitchen):
        return None
    load = len(apps) + (1 if _has(washer) and "المطبخ" in str(washer) else 0)
    if load < 4:
        return None
    basis = [("المطبخ مفتوح", kitchen), ("أجهزة المطبخ", apps)]
    if _has(washer):
        basis.append(("مكان الغسالة", washer))
    return {
        "severity": "medium",
        "title": "مطبخ مقفول بحمل أجهزة عالي",
        "detail": "عدد الأجهزة ده محتاج مساحة وأطوال شغل حقيقية. يتقاس على المخطط قبل الوعد بالتوزيع.",
        "basis": basis,
        "question": None,
    }


def _r_family_will_grow(a):
    v = _get(a, "بعد ٥ سنين")
    if not _has(v):
        return None
    text = str(v)
    if "هتكبر" not in text and "الأهل" not in text and "مرن" not in text:
        return None
    return {
        "severity": "medium",
        "title": "البيت محتاج يستحمل تغيير بعد سنين",
        "detail": "أوضة بتتحول لأوضة تانية بتتصمم مختلف من أول يوم: البريز والإنارة والتخزين.",
        "basis": [("بعد ٥ سنين", v)],
        "question": "أنهي أوضة الأقرب إنها تتغير وظيفتها؟",
    }


def _r_warm_classic_no_ornament(a):
    style = _get(a, "مودرن ولا دافي كلاسيك")
    bans = _as_list(_get(a, "ممنوعات"))
    if not _has(style) or "كلاسيك" not in str(style):
        return None
    conflicting = [b for b in bans if ("كلاسيك" in str(b) or "زخارف" in str(b)
                                       or "نقوش" in str(b) or "دهبي" in str(b))]
    if not conflicting:
        return None
    return {
        "severity": "low",
        "title": "اتجاه واضح: الدفا من النسب والخامة مش من الزخرفة",
        "detail": "اختيار الكلاسيك الدافي مع منع الزخرفة والكلاسيك التقيل بيحدد الاتجاه بدقة، مش تعارض.",
        "basis": [("مودرن ولا دافي كلاسيك", style), ("ممنوعات", conflicting)],
        "question": None,
    }


def _r_wfh_without_detail(a):
    wfh = _get(a, "شغل من البيت")
    detail = _get(a, "تفاصيل المكتب")
    if not _has(wfh) or "يومياً" not in str(wfh):
        return None
    if _has(detail):
        return None
    return {
        "severity": "low",
        "title": "شغل يومي من البيت من غير تفاصيل المكتب",
        "detail": "المكتب اليومي محتاج مقاسات وتخزين وإنارة مهام، والإجابة فاضية.",
        "basis": [("شغل من البيت", wfh)],
        "question": "المكتب محتاج إيه؟ (شاشات، اجتماعات فيديو، مكتبة، تخزين)",
    }


def _r_bare_shell_timeline(a):
    state = _get(a, "حالة الوحدة")
    service = _get(a, "الخدمة")
    if not _has(state) or "الطوب" not in str(state):
        return None
    if not _has(service) or "تنفيذ" not in str(service):
        return None
    return {
        "severity": "low",
        "title": "على الطوب + تصميم وتنفيذ = المدد والدفعات لازم تتقال بدري",
        "detail": "الشغل من الصفر معناه مراحل كاملة ومدد توريد. الجدول الزمني والدفعات يتحطوا في العرض الأول.",
        "basis": [("حالة الوحدة", state), ("الخدمة", service)],
        "question": None,
    }


RULES = [
    ("budget_scope", _r_budget_scope),
    ("privacy_guests", _r_privacy_vs_guests),
    ("girl_among_boys", _r_girl_among_boys),
    ("kitchen_contradiction", _r_kitchen_contradiction),
    ("ramadan_peak", _r_ramadan_peak),
    ("light_palette_load", _r_light_palette_load),
    ("closed_kitchen_appliances", _r_closed_kitchen_appliances),
    ("family_will_grow", _r_family_will_grow),
    ("wfh_without_detail", _r_wfh_without_detail),
    ("warm_classic_no_ornament", _r_warm_classic_no_ornament),
    ("bare_shell_timeline", _r_bare_shell_timeline),
]

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}

# الحقائق اللي بتتنقل حرفيًا في رأس القراءة
_FACT_KEYS = [
    "نوع الوحدة", "حالة الوحدة", "الخدمة",
    "الميزانية", "شمول الميزانية", "أولوية التضحية",
    "عدد الأفراد", "أطفال", "تفاصيل الأطفال",
    "شكل العزومة", "عدد العزومة", "عزومات رمضان",
    "ممنوعات", "ممنوعات إضافية",
]

# اللي غيابه بيوقف الشغل فعلاً
_CRITICAL_KEYS = ["الميزانية", "شمول الميزانية", "نوع الوحدة", "ممنوعات"]


def read_brief(row):
    """صف استبيان -> قراءة تصميمية مفصولة (حقائق / استنتاجات / أسئلة).

    بترجع dict دايمًا -- مفيش None هنا لأن ده حساب محلي مش قراءة شبكة.
    """
    answers = (row or {}).get("answers") or {}

    facts = [(k, answers[k]) for k in _FACT_KEYS if _has(answers.get(k))]

    flags = []
    for rule_id, fn in RULES:
        try:
            out = fn(answers)
        except Exception as e:                                  # pragma: no cover
            logger.error(f"❌ [brief_reader] قاعدة {rule_id} رمت استثناء: {e}")
            continue
        if out:
            out["id"] = rule_id
            out.setdefault("source", "البريف")
            flags.append(out)
    flags.sort(key=lambda f: _SEV_ORDER.get(f.get("severity"), 3))

    questions = [f["question"] for f in flags if f.get("question")]

    missing = [k for k in _CRITICAL_KEYS if not _has(answers.get(k))]

    return {
        "facts": facts,
        "flags": flags,
        "questions": questions,
        "missing": missing,
        "is_final": bool((row or {}).get("is_final")),
    }


# ============================================================
# العرض
# ============================================================

_SEV_ICON = {"high": "🔴", "medium": "🟠", "low": "⚪"}


def _fmt(v):
    if isinstance(v, list):
        return "، ".join(str(x) for x in v)
    return str(v)


def format_read(row, read=None):
    """قراءة -> نص تليجرام.

    بنية النص بتنفذ الفصل الدستوري حرفيًا: الحقائق تحت عنوانها، والاستنتاجات
    تحت عنوان "استنتاج" وكل واحد جنبه "مبني على"، والأسئلة أسئلة.
    """
    read = read or read_brief(row)
    a = (row or {}).get("answers") or {}
    name = (row or {}).get("client_name") or a.get("الاسم") or "من غير اسم"

    out = [f"🔍 قراءة بريف — {name}"]

    if not read["is_final"]:
        out.append("⏸️ البريف لسه مكملش — القراءة على الموجود بس.")

    if read["missing"]:
        out.append("❔ ناقص: " + "، ".join(read["missing"]))

    if read["facts"]:
        out.append("\n📌 اللي اتقال:")
        out += [f"• {k}: {_fmt(v)}" for k, v in read["facts"]]

    if read["flags"]:
        out.append("\n🧠 استنتاج (مش كلام العميل):")
        for f in read["flags"]:
            icon = _SEV_ICON.get(f.get("severity"), "⚪")
            tag = " · 🖋️ توقيعك" if f.get("source") == "توقيعك" else ""
            out.append(f"\n{icon} {f['title']}{tag}")
            if f.get("rule"):
                out.append(f"   قاعدتك: «{f['rule']}»")
            out.append(f"   {f['detail']}")
            basis = "، ".join(f"{k}: {_fmt(v)}" for k, v in f["basis"])
            out.append(f"   ↳ مبني على — {basis}")

    if read["questions"]:
        out.append("\n❓ تسأله في المعاينة:")
        out += [f"• {q}" for q in read["questions"]]

    if not read["flags"] and not read["questions"]:
        out.append("\nمفيش توترات ظاهرة في الإجابات دي.")

    return "\n".join(out)
