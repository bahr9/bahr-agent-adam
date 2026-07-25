# -*- coding: utf-8 -*-
"""
🧾 Truth Layer -- ADAM Self-State & Observation System (Architecture v2, Phase 1)
=====================================================
أول طبقة من Truth → Meaning → Companionship. بتغلّف نفس البنية التحتية
الموجودة فعليًا (self_state_engine.py, event_store.py -- Stage 1/5) بعقد
أصرم: كل حقيقة (TruthFact) لازم يكون ليها مصدر واضح، ومفيش قيمة بتدخل
الـ packet من غير مصدر.

القاعدة الحاكمة (المبدأ السابع): "آدم يستطيع التفكير في الحقائق المثبتة،
لكنه لا يستطيع إنشاء حقائق جديدة يُبنى عليها التفكير." -- الملف ده هو
نقطة الفرض الأولى لهذا المبدأ: أي TruthFact بدون مصدر صريح **ترفض وقت
البناء نفسه**، مش تنقية بعد كده (نفس فلسفة event_store.InvalidEventError).

أنواع المصادر (FactSource) -- التلاتة دول بس، مفيش رابع:
  - "event_evidence": مبنية على أحداث حقيقية في adam_events. evidence_event_ids إجبارية وغير فاضية.
  - "static_schedule": مبنية على بيانات ثابتة معروفة (زي جدول الأقساط). evidence_event_ids ممنوعة (مفيش أحداث أصلًا).
  - "derived": محسوبة من TruthFact تاني في نفس الـ packet. derived_from_field إجباري ويشاور لحقل موجود فعليًا.

تحقق الـ derived facts (Phase 1 -- Tests First، test_truth_layer.py):
  الـ Schema Validator هنا بيتأكد من **صحة الربط** (derived_from_field
  موجود فعليًا) دايمًا. لحالة خاصة وشائعة جدًا -- حقل integer مشتق من حقل
  list (زي count = len(overdue_items)) -- بيتفحص كمان **تطابق العدد
  فعليًا** (فحص حتمي رخيص لنمط محدد، مش تحقق عام لأي صيغة حسابية). أي
  صيغة حساب تانية أعقد من كده تفضل مسؤولية دالة compute_* نفسها واختباراتها،
  مش الـ Schema.
"""

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from utils.time_utils import now_cairo

VALID_SOURCES = {"event_evidence", "static_schedule", "derived"}
VALID_CERTAINTY = {"exact", "approximate"}


class InvalidTruthFactError(ValueError):
    """بترفع وقت بناء TruthFact لو مصدره أو نوعه غير متسق -- الرفض هنا، مش بعد كده."""
    pass


@dataclass
class TruthFact:
    field: str
    type: str                       # "integer" | "enum" | "boolean" | "date" | "string" | "list"
    value: object
    source: str                     # "event_evidence" | "static_schedule" | "derived"
    evidence_event_ids: list = field(default_factory=list)
    computed_by: str = ""
    computation_version: str = "v1"
    derived_from_field: Optional[str] = None
    allowed_values: Optional[list] = None
    certainty: str = "exact"        # "exact" | "approximate"


@dataclass
class TruthPacket:
    truth_packet_id: str
    domain: str
    derived_at: str                 # ISO timestamp
    ttl_seconds: int
    facts: list                     # list[TruthFact]
    integrity: dict                 # {"computation_errors": [...], "partial": bool}


def build_truth_fact(
    field: str,
    type_: str,
    value,
    source: str,
    evidence_event_ids: Optional[list] = None,
    computed_by: str = "",
    computation_version: str = "v1",
    derived_from_field: Optional[str] = None,
    allowed_values: Optional[list] = None,
    certainty: str = "exact",
) -> TruthFact:
    """
    بناء TruthFact + رفض فوري لو مصدره أو نوعه غير متسق. القيود دي مش
    اقتراحية -- أي مخالفة بترفع InvalidTruthFactError، مفيش حقيقة "تمر
    مؤقتًا" وتتصحح بعدين.
    """
    evidence_event_ids = evidence_event_ids or []

    if source not in VALID_SOURCES:
        raise InvalidTruthFactError(f"{field}: source='{source}' مش من ضمن {VALID_SOURCES}")
    if certainty not in VALID_CERTAINTY:
        raise InvalidTruthFactError(f"{field}: certainty='{certainty}' مش من ضمن {VALID_CERTAINTY}")

    if source == "event_evidence" and not evidence_event_ids:
        raise InvalidTruthFactError(f"{field}: source=event_evidence لازم evidence_event_ids غير فاضية")
    if source == "static_schedule" and evidence_event_ids:
        raise InvalidTruthFactError(f"{field}: source=static_schedule مينفعش يكون له evidence_event_ids")
    if source == "derived" and not derived_from_field:
        raise InvalidTruthFactError(f"{field}: source=derived لازم derived_from_field يحدد الحقل المصدري")

    if type_ == "enum":
        if not allowed_values:
            raise InvalidTruthFactError(f"{field}: نوعه enum لازم allowed_values محددة")
        if value not in allowed_values:
            raise InvalidTruthFactError(f"{field}: القيمة {value!r} مش من ضمن allowed_values={allowed_values}")

    return TruthFact(
        field=field, type=type_, value=value, source=source,
        evidence_event_ids=evidence_event_ids, computed_by=computed_by,
        computation_version=computation_version, derived_from_field=derived_from_field,
        allowed_values=allowed_values, certainty=certainty,
    )


def validate_truth_packet(packet: TruthPacket) -> list:
    """
    تحقق بنيوي حتمي 100%. يرجع قايمة أخطاء -- فاضية يعني الـ packet سليم.
    مبيرفعش استثناء -- القرار (نستخدم الـ packet ولا نرفضه) بيرجع لمين
    بينادي الدالة دي (Meaning Layer لاحقًا).
    """
    errors = []
    facts_by_field = {f.field: f for f in packet.facts}

    for fact in packet.facts:
        if fact.source == "event_evidence" and not fact.evidence_event_ids:
            errors.append(f"{fact.field}: event_evidence بدون evidence_event_ids")

        if fact.source == "static_schedule" and fact.evidence_event_ids:
            errors.append(f"{fact.field}: static_schedule ومعاه evidence_event_ids (تناقض)")

        if fact.source == "derived":
            if not fact.derived_from_field:
                errors.append(f"{fact.field}: source=derived بدون derived_from_field")
            elif fact.derived_from_field not in facts_by_field:
                errors.append(
                    f"{fact.field}: derived_from_field='{fact.derived_from_field}' "
                    f"مش موجود في نفس الـ packet"
                )
            else:
                source_fact = facts_by_field[fact.derived_from_field]
                # الحالة الخاصة الشائعة: integer مشتق من list -- فحص count == len(list) حتمي
                if fact.type == "integer" and source_fact.type == "list":
                    if fact.value != len(source_fact.value):
                        errors.append(
                            f"{fact.field}: value={fact.value} لكن len({fact.derived_from_field})="
                            f"{len(source_fact.value)} -- تناقض في derived fact"
                        )

        if fact.type == "enum" and fact.allowed_values and fact.value not in fact.allowed_values:
            errors.append(f"{fact.field}: القيمة {fact.value!r} مش من ضمن allowed_values")

    return errors


def truth_packet_confidence(packet: TruthPacket) -> str:
    """"full" لو الحساب كامل، "degraded" لو integrity.partial=True. مصدر Meaning Confidence مباشرة (v2، قسم 6)."""
    return "degraded" if packet.integrity.get("partial") else "full"


def is_stale(packet: TruthPacket) -> bool:
    """TTL check -- لو عمر الـ packet أكبر من ttl_seconds، يُعتبر قديم ولازم يتحسب من جديد."""
    from datetime import datetime
    derived_at = datetime.fromisoformat(packet.derived_at)
    age_seconds = (now_cairo() - derived_at).total_seconds()
    return age_seconds > packet.ttl_seconds


def build_truth_packet_for_loans() -> TruthPacket:
    """
    الربط الفعلي مع البنية الموجودة (self_state_engine.py، Stage 5) --
    بيحوّل ناتج compute_self_state() الحالي لـ TruthPacket رسمي بنفس
    العقد. مفيش إعادة حساب -- نفس الدوال المعتمدة والمتحقق منها فعليًا.
    """
    from services import self_state_engine

    self_state = self_state_engine.compute_self_state()
    facts = []

    conflict = self_state["unresolved_conflict"]
    facts.append(build_truth_fact(
        field="unresolved_conflict.count", type_="integer", value=conflict["count"],
        source="event_evidence" if conflict["count"] > 0 else "static_schedule",
        evidence_event_ids=conflict["evidence_event_ids"],
        computed_by="self_state_engine.compute_unresolved_conflict",
    ))
    facts.append(build_truth_fact(
        field="unresolved_conflict.level", type_="enum", value=conflict["level"],
        source="event_evidence" if conflict["count"] > 0 else "static_schedule",
        evidence_event_ids=conflict["evidence_event_ids"],
        computed_by="self_state_engine.compute_unresolved_conflict",
        allowed_values=["none", "elevated", "high"],
    ))

    obligation = self_state["pending_obligation_load"]
    facts.append(build_truth_fact(
        field="pending_obligation_load.overdue_items", type_="list", value=obligation["overdue_items"],
        source="static_schedule", computed_by="self_state_engine.compute_pending_obligation_load",
    ))
    facts.append(build_truth_fact(
        field="pending_obligation_load.count", type_="integer", value=obligation["count"],
        source="derived", derived_from_field="pending_obligation_load.overdue_items",
        computed_by="self_state_engine.compute_pending_obligation_load",
    ))
    facts.append(build_truth_fact(
        field="pending_obligation_load.level", type_="enum", value=obligation["level"],
        source="derived", derived_from_field="pending_obligation_load.count",
        computed_by="self_state_engine.compute_pending_obligation_load",
        allowed_values=["none", "light", "concern"],
    ))

    stability = self_state["tracking_stability"]
    facts.append(build_truth_fact(
        field="tracking_stability.count", type_="integer", value=stability["count"],
        source="event_evidence" if stability["count"] > 0 else "static_schedule",
        evidence_event_ids=stability["evidence_event_ids"],
        computed_by="self_state_engine.compute_tracking_stability",
    ))
    facts.append(build_truth_fact(
        field="tracking_stability.level", type_="enum", value=stability["level"],
        source="event_evidence" if stability["count"] > 0 else "static_schedule",
        evidence_event_ids=stability["evidence_event_ids"],
        computed_by="self_state_engine.compute_tracking_stability",
        allowed_values=["none", "frequent_corrections"],
    ))

    return TruthPacket(
        truth_packet_id=str(uuid.uuid4()),
        domain="loans",
        derived_at=self_state["computed_at"],
        ttl_seconds=300,
        facts=facts,
        integrity={"computation_errors": [], "partial": False},
    )
