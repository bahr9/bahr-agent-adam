# -*- coding: utf-8 -*-
"""
✅ Claim Validator -- ADAM Self-State & Observation System (Architecture v2)
=====================================================
يفحص *template* Companionship (قبل الرندر، مش بعده) قبل ما يوصل لأحمد. بعد
الرندر فيه أرقام حقيقية شرعية من الـslots -- فحص وقتها مش هيميّز بين رقم
حقيقي ورقم مخترع، فلازم الفحص يحصل على النص الخام اللي كتبه الموديل.

الفحوصات (Tests First -- test_claim_validator.py):
  1. صفر رقم خام برّه أي slot (حتمي 100%) -- بصرف النظر عن صحته الرقمية.
  2. صفر كلمة تقريب لاصقة بقيمة مؤكدة (slot أو رقم خام) -- heuristic.
  3. صفر نمط نفي قاطع (نفي + مؤكِّد إطلاق زي "خالص") -- heuristic، أضيق
     عمدًا من أي نفي عام عشان ميتفلترش كلام عادي زي "مفيش حاجة جديدة
     النهاردة" (نفي بلا مؤكِّد إطلاق = كلام عادي، مش ادّعاء قاطع).
  4. صفر ادّعاء طمأنة/حالة حر (زي "كله تمام"، "مفيش داعي للقلق") -- heuristic.
     طلب صريح من أحمد بعد ملاحظة إن الموديل ممكن "يخترع خلاصة مطمئنة"
     من غير ما يكون فيه دليل يسمح بيها أصلًا -- حتى لو مفيش رقم أو نفي
     قاطع فيها. الطمأنة المرخّصة الوحيدة: نص inference معتمد سلفًا،
     متلصق عبر Slot -- مش متأليف حر (نفس منطق البند 3، بس على مساحة
     أوسع من مجرد النفي).
  5. صفر تناقض حل/إغلاق حر (زي "محلولة"، "اتحلت") لبُعد عنده count فعلي
     موثّق (> 0) -- heuristic منفصل عن بند 4. اتكشف من تشغيلة تكامل حقيقية
     (test_pipeline_integration.py): الموديل كتب "خلافات لسه متفتحة
     ومحلولة" -- تناقض وقائعي مباشر مع unresolved_conflict.count=1 الموثّق،
     من غير ما يستخدم أي رقم خام أو نمط طمأنة من بند 4. الفرق عن بند 4:
     ده مش "طمأنة عامة غير مرخّصة"، ده تناقض مباشر مع حقيقة موثّقة فعليًا
     في نفس الـMeaning Packet.
  6. كل الـslots المستخدمة لازم تكون فعليًا موجودة في الـMeaning Packet --
     بيتفحص عبر محاولة render فعلية (services/renderer.py).

صفر LLM هنا -- فحص نصي حتمي/heuristic بحت. rendered_text بيتملي بس لو
valid=True (كل الفحوصات عدّت وكل الـslots اتفكّت صح).

---
قيد بنيوي موثّق (اعتماد أحمد 2026-07-24، مش خطأ لسه محتاج إصلاح):

تشغيلة تكامل حقيقية (test_pipeline_integration.py) طلّعت نفس تناقض
"الحل/الإغلاق" (بند 5) **مرتين من 3 تشغيلات مستقلة**، بكلمتين مختلفتين
("محلولة" ثم "محسومة") لنفس المعنى بالظبط. دي مش صدفة معزولة -- دليل تنفيذي
حقيقي إن أي قائمة كلمات منسّقة (curated) هتفضل دايمًا خطوة ورا موديل بيولّد
مرادفات جديدة لنفس الفكرة. **الحد ده مسجّل عمدًا، مش هدف نلاحقه بإضافة
كلمات لا نهائيًا** -- أي مرادف تالت يظهر مستقبلًا يُسجَّل ويُصلَّح بنفس
الطريقة (Red test بالنص الحقيقي، fix مستهدف)، لكن مفيش وهم إننا هنوصل
لتغطية كاملة بقائمة كلمات. هذا الدليل مسجَّل رسميًا كأول نقطة بيانات نحو
مراجعة مستقبلية لقرار Level A/B (انظر EXPRESSIVE_VOICE_RECONSIDERATION_
DRAFT.md، قسم "سجل الأدلة") -- مش سبب لإعادة تصميم الاستراتيجية الحالية الآن.
"""

import re

from services.renderer import render, UnknownSlotError, SLOT_PATTERN

APPROXIMATION_PATTERNS = [r"حوالي", r"تقريبًا", r"تقريبا", r"يمكن", r"غالبًا", r"غالبا", r"في\s+حدود"]
NEGATION_TRIGGERS = [r"مفيش", r"لا\s+يوجد", r"معدوم"]
NEGATION_INTENSIFIERS = [r"خالص", r"إطلاقًا", r"إطلاقا", r"نهائي", r"أبدًا", r"أبدا"]

# ادّعاءات طمأنة/حالة عامة -- heuristic موثّق صراحة كقائمة محدودة، مش تغطية
# دلالية كاملة. أي صياغة تانية بنفس المعنى مش في القائمة دي ممكن تفلت --
# ده حد الأداة الحالية، مش ادّعاء بضمان كامل (زي باقي الفحوصات الـheuristic
# في المشروع ده).
STATUS_CLAIM_PATTERNS = [
    r"كله\s+تمام",
    r"كل\s+حاجة\s+تمام",
    r"الوضع\s+تمام",
    r"الوضع\s+مستقر",
    r"الأمور\s+مستقرة",
    r"مفيش\s+(أي\s+)?مشكل[ةه]",
    r"مفيش\s+داعي\s+للقلق",
    r"مفيش\s+حاجة\s+تقلق",
    r"متقلقش",
]

# كلمات تدّعي إن موضوع بُعد معيّن "اتحل/اتقفل/اتسدد" -- تناقض مباشر لو
# الحقيقة المرخّصة بتقول إن نفس البُعد لسه له count فعلي (> 0). مقصود
# نطاقها ضيق: بس الأبعاد اللي فعلاً عندها معنى "لسه قائم مقابل اتحل"
# (unresolved_conflict, pending_obligation_load) -- tracking_stability
# معندهاش معنى "اتحل" مشابه فمش مذكور هنا.
RESOLUTION_CONTRADICTION_WORDS = {
    "unresolved_conflict": [
        r"محلول[ةه]?", r"اتحل[توا]?", r"مقفول[ةه]?", r"اتقفل[توا]?",
        r"خلص[توا]?", r"انتهى", r"محسوم[ةه]?", r"اتحسم[توا]?",
    ],
    "pending_obligation_load": [r"اتسدد[توا]?", r"مدفوع[ةه]?", r"خلص[توا]?", r"اتقفل[توا]?"],
}

_PROXIMITY_WINDOW = 20


def _mask_slots(text: str) -> str:
    """يستبدل كل {slot} بمسافات بنفس الطول -- عشان فحص الأرقام يتجاهل أسماء الحقول جوه الأقواس."""
    return SLOT_PATTERN.sub(lambda m: " " * len(m.group(0)), text)


def _check_raw_digits(masked: str) -> list:
    """أي رقم خام برّه أي slot -- رفض حتمي، بصرف النظر عن صحته الرقمية."""
    return [
        {
            "type": "deterministic",
            "message": f"رقم خام '{m.group(0)}' خارج أي slot -- غير مسموح، لازم يتحط جوه slot معتمد",
        }
        for m in re.finditer(r"\d+", masked)
    ]


def _check_approximation(template: str, masked: str) -> list:
    """كلمة تقريب لاصقة بقيمة مؤكدة (slot أو رقم خام) -- heuristic."""
    anchors = [m.span() for m in SLOT_PATTERN.finditer(template)]
    anchors += [m.span() for m in re.finditer(r"\d+", masked)]

    errors = []
    for pat in APPROXIMATION_PATTERNS:
        for m in re.finditer(pat, template):
            if any(
                (a_start - _PROXIMITY_WINDOW) <= m.start() <= (a_end + _PROXIMITY_WINDOW)
                for a_start, a_end in anchors
            ):
                errors.append({
                    "type": "heuristic",
                    "message": f"كلمة تقريب '{m.group(0)}' قريبة من قيمة مؤكدة -- الحقيقة الأصلية exact مش approximate",
                })
    return errors


def _check_free_negation(template: str) -> list:
    """نمط نفي قاطع (نفي + مؤكِّد إطلاق) -- heuristic أضيق من نفي عام، عشان ميتفلترش كلام عادي."""
    trigger_spans = [m.span() for pat in NEGATION_TRIGGERS for m in re.finditer(pat, template)]
    intensifier_spans = [m.span() for pat in NEGATION_INTENSIFIERS for m in re.finditer(pat, template)]

    errors = []
    for t_start, t_end in trigger_spans:
        for i_start, i_end in intensifier_spans:
            if abs(i_start - t_end) <= _PROXIMITY_WINDOW * 2 or abs(t_start - i_end) <= _PROXIMITY_WINDOW * 2:
                errors.append({
                    "type": "heuristic",
                    "message": (
                        f"نمط نفي قاطع '{template[t_start:t_end]} ... {template[i_start:i_end]}' "
                        "-- تأكيد مطلق محتاج مراجعة"
                    ),
                })
    return errors


def _check_unlicensed_status_claims(template: str) -> list:
    """
    ادّعاء طمأنة/حالة حر (زي "كله تمام"، "مفيش داعي للقلق") -- heuristic.
    بيفحص النص الخام (قبل الرندر) بس -- لو الطمأنة جاية من داخل نص
    inference معتمد (عبر {inference:rule_id})، مش هتظهر في التمبليت نفسه
    خالص (بتتلصق وقت الرندر بس)، فمش هتتفحص هنا أصلًا -- نفس آلية الإفلات
    السليم اللي بند 3 (النفي القاطع) بيعتمد عليها.
    """
    return [
        {
            "type": "heuristic",
            "message": f"ادّعاء طمأنة/حالة غير مرخّص '{m.group(0)}' -- لازم يجي من inference معتمد عبر Slot، مش نص حر",
        }
        for pat in STATUS_CLAIM_PATTERNS
        for m in re.finditer(pat, template)
    ]


def _check_resolution_contradiction(template: str, meaning_packet: dict) -> list:
    """
    نمط تناقض حل/إغلاق حر -- heuristic. لو الحقيقة المرخّصة بتقول إن البُعد
    لسه له count فعلي (> 0)، أي كلمة حرة في التمبليت بتدّعي إنه "اتحل/اتقفل"
    تناقض مباشر مع الحقيقة الموثّقة -- بصرف النظر عن عدم تطابقها مع قائمة
    الطمأنة العامة (STATUS_CLAIM_PATTERNS). لو مفيش count موثّق للبُعد ده
    أصلًا (أو كان صفر)، مفيش حقيقة تتناقض معاها، فمفيش فحص يحصل.
    """
    referenced = meaning_packet.get("referenced_facts", {})
    errors = []
    for dimension, patterns in RESOLUTION_CONTRADICTION_WORDS.items():
        count = referenced.get(f"{dimension}.count")
        if not count:
            continue
        for pat in patterns:
            for m in re.finditer(pat, template):
                errors.append({
                    "type": "heuristic",
                    "message": (
                        f"تناقض حل/إغلاق: '{m.group(0)}' بيتناقض مع {dimension}.count={count} "
                        "الموثّق -- لغة الحل/الإغلاق لازم تيجي من slot أو inference معتمد، مش نص حر"
                    ),
                })
    return errors


def validate_companionship_output(template: str, meaning_packet: dict) -> dict:
    """
    يفحص template Companionship الخام قبل أي إرسال. يرجع:
      {"valid": bool, "errors": [{"type": "deterministic"|"heuristic", "message": str}], "rendered_text": str|None}
    """
    masked = _mask_slots(template)

    errors = []
    errors.extend(_check_raw_digits(masked))
    errors.extend(_check_approximation(template, masked))
    errors.extend(_check_free_negation(template))
    errors.extend(_check_unlicensed_status_claims(template))
    errors.extend(_check_resolution_contradiction(template, meaning_packet))

    rendered = None
    try:
        rendered = render(template, meaning_packet)
    except UnknownSlotError as e:
        errors.append({"type": "deterministic", "message": f"slot غير معروف: {e}"})

    valid = len(errors) == 0
    return {
        "valid": valid,
        "errors": errors,
        "rendered_text": rendered if valid else None,
    }
