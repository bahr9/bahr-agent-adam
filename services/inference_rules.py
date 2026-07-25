# -*- coding: utf-8 -*-
"""
📐 Inference Rules -- ADAM Self-State & Observation System (Architecture v2)
=====================================================
قواعد الاستنتاج الثابتة في الـbackend -- بتحوّل TruthPacket لقائمة استنتاجات
"اتفعّلت" فعليًا (fired rules) حسب شروط صريحة. صفر LLM، صفر تخمين.

الواجهة (`evaluate_fired_rules`) معرَّفة أصلًا من TRUTH_MEANING_COMPANIONSHIP_
ARCHITECTURE.md (قسم 8) -- هذا الملف تنفيذ لعقد موجود من قبل، مش تصميم جديد.

نطاق حالي: 3 قواعد بس، تغطي نفس البُعدين المفعّلين في self_state_engine.py
(unresolved_conflict له قاعدتين حسب الشدة high/elevated، وpending_obligation_load
له قاعدة واحدة) -- كافي لسيناريو التكامل الحالي. كل قاعدة فيها `priority` و`version` (زي ما اتحدد في
TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md قسم 5) استعدادًا لأي Rule
Engine مستقبلي، من غير ما نبنيه فعليًا دلوقتي (over-engineering مؤجّل عمدًا
لحد ما عدد القواعد يوصل لعشرات فعليًا).
"""

INFERENCE_RULES = [
    {
        "rule_id": "unresolved_conflict_high",
        "domain": "loans",
        "dimension": "unresolved_conflict",
        "priority": 10,
        "version": "v1",
        "condition": lambda facts: facts.get("unresolved_conflict.level") == "high",
        "text": "الوضع محتاج مراجعة عاجلة",
        "claims": ["severity_high"],
    },
    {
        "rule_id": "unresolved_conflict_elevated",
        "domain": "loans",
        "dimension": "unresolved_conflict",
        "priority": 5,
        "version": "v1",
        "condition": lambda facts: facts.get("unresolved_conflict.level") == "elevated",
        "text": "محتاج مراجعتك",
        "claims": ["severity_elevated"],
    },
    {
        "rule_id": "pending_obligation_concern",
        "domain": "loans",
        "dimension": "pending_obligation_load",
        "priority": 10,
        "version": "v1",
        "condition": lambda facts: facts.get("pending_obligation_load.level") == "concern",
        "text": "الوضع محتاج متابعة قريبة",
        "claims": ["severity_concern"],
    },
]


def evaluate_fired_rules(packet) -> list:
    """
    يرجع كل القواعد اللي شرطها True فعليًا بناءً على حقائق TruthPacket
    المُعطى. بيرجع نسخة من كل قاعدة بدون مفتاح "condition" (مش قابل
    للتسلسل، ومش محتاج يوصل لـMeaning/Companionship أصلًا).
    """
    facts = {f.field: f.value for f in packet.facts}
    return [
        {k: v for k, v in rule.items() if k != "condition"}
        for rule in INFERENCE_RULES
        if rule["domain"] == packet.domain and rule["condition"](facts)
    ]
