# -*- coding: utf-8 -*-
"""
🧩 Meaning Layer -- ADAM Self-State & Observation System (Architecture v2)
=====================================================
تاني طبقة من Truth → Meaning → Companionship. **Backend بحت، صفر LLM
خالص** (قرار مقفول، v2 قسم 1): الحقائق موجودة في الـ backend، وقواعد
الاستنتاج موجودة في الـ backend، فالفلترة والترتيب بينهم عملية ميكانيكية
بحتة -- مفيش "فهم" حقيقي محتاج نموذج لغوي.

الدالة الأساسية هنا (`compute_meaning_packet`) دالة حتمية خالصة: نفس
المدخلات (TruthPacket + target_dimensions + fired_rules) بتدّي نفس
المخرجات بالظبط، كل مرة، بدون استثناء. أي كود جديد في الملف ده لازم
يفضل ملتزم بالقاعدة دي -- ممنوع أي استدعاء LLM أو أي مصدر عشوائية/احتمالية
يدخل هنا.
"""

from typing import Union

# ترتيب الأولوية بين الأبعاد -- Priority Scores (معتمد 2026-07-24، مش مجرد
# ترتيب ثابت). رقم أعلى = أولوية أعلى. أي بُعد جديد لازم ياخد Score صريح هنا.
DIMENSION_PRIORITY = {
    "unresolved_conflict": 30,
    "pending_obligation_load": 20,
    "tracking_stability": 10,
}


class InvalidMeaningRequestError(ValueError):
    """بترفع لو target_dimension مش معروف أصلًا، أو معروف لكن مش موجود في الـ Truth Packet المُعطى."""
    pass


def _available_dimensions(truth_packet) -> set:
    return {f.field.split(".")[0] for f in truth_packet.facts}


def compute_meaning_packet(truth_packet, target_dimensions: Union[str, list], fired_rules: list) -> dict:
    """
    فلترة وترتيب بحت -- مفيش LLM. بترجع Meaning Packet:
      referenced_facts, fired_inferences, primary_focus, secondary_focus,
      priority_order, confidence, allowed_topics.

    target_dimensions: بُعد واحد (str) أو أكتر (list) -- لو أكتر من واحد،
    بيترتبوا حسب DIMENSION_PRIORITY، والأعلى بيبقى primary_focus.
    """
    from services.truth_layer import truth_packet_confidence

    if isinstance(target_dimensions, str):
        target_dimensions = [target_dimensions]

    available = _available_dimensions(truth_packet)
    for dim in target_dimensions:
        if dim not in DIMENSION_PRIORITY:
            raise InvalidMeaningRequestError(f"'{dim}' مش بُعد معروف/مسموح (مش موجود في DIMENSION_PRIORITY)")
        if dim not in available:
            raise InvalidMeaningRequestError(f"'{dim}' مش موجود في الـ Truth Packet المُعطى")

    # 5) ترتيب حسب priority_order -- ثابت، مستقل عن ترتيب الطلب
    sorted_dims = sorted(set(target_dimensions), key=lambda d: -DIMENSION_PRIORITY[d])

    # 1) فلترة الـ facts حسب الأبعاد المطلوبة بس
    referenced_facts = {
        f.field: f.value for f in truth_packet.facts
        if f.field.split(".")[0] in sorted_dims
    }

    # 2) فلترة fired_inferences بالـ domain الصحيح وبالبُعد المطلوب سوا
    fired_inferences = [
        r for r in fired_rules
        if r.get("domain") == truth_packet.domain and r.get("dimension") in sorted_dims
    ]

    # 3) primary_focus / allowed_topics -- حتمي بالكامل من الترتيب
    primary_focus = sorted_dims[0]
    secondary_focus = sorted_dims[1:]
    allowed_topics = list(sorted_dims)

    # 4) confidence -- بترث من Truth Packet زي ما هي، صفر حساب إضافي
    confidence = truth_packet_confidence(truth_packet)

    return {
        "referenced_facts": referenced_facts,
        "fired_inferences": fired_inferences,
        "primary_focus": primary_focus,
        "secondary_focus": secondary_focus,
        "priority_order": sorted_dims,
        "confidence": confidence,
        "allowed_topics": allowed_topics,
    }
