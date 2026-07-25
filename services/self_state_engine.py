# -*- coding: utf-8 -*-
"""
🧠 Self-State Engine -- ADAM Self-State & Observation System (Stage 5 + 5.1)
=====================================================
الطبقتين الأوليين من المعمارية:

    Events → [State Derivation Engine → Self-State] → Decision Engine → Expression

المبدأ الخامس في دستور آدم: **"الحالة الداخلية ليست رأيًا، بل نتيجة حسابية
قابلة للتفسير."** كل بُعد هنا لازم يكون له evidence_event_ids حقيقية من
الـ Event Store، أو تفسير صريح لو جزء من الدليل مش event (زي جدول الأقساط
الثابت + التاريخ الحالي). مفيش أي مساحة لتخمين LLM هنا -- قواعد Python
صريحة بس.

**القاعدة الأهم: الحالة Domain-Independent.** الأبعاد بتتكلم عن آدم نفسه
(uncertainty/pending obligations)، مش عن "الأقساط" كموضوع. الأقساط دلوقتي
هي *مصدر البيانات* الوحيد (لأنها المجال الوحيد اللي عنده Event Store +
Observer + Conflict Resolution شغالين -- مراحل 1-4)، مش موضوع الحالة.

نطاق v0.1 (معتمد من أحمد بتاريخ 2026-07-24):
  - unresolved_conflict: none/elevated/high -- high عند 3 تعارضات معلّقة.
  - pending_obligation_load: none/light/concern -- concern عند 2 قسط متأخر.
    (عتبة أقل من التعارضات عمدًا: مبدأ معتمد -- أبعاد بتمس التزامات مالية
    حقيقية عتبتها أقل من أبعاد منطقية/تقنية زي التعارضات.)
  - tracking_stability: none/frequent_corrections -- عند 5 تصحيحات صريحة
    (loan_update_installment) في آخر 30 يوم عبر كل الأقساط (معتمد 2026-07-24).
    **ملحوظة مهمة (مقصودة):** التصحيح الموثّق بسبب هو سلوك حوكمة *صحي* --
    البُعد ده بيوصف معدل موضوعي، مش "مشكلة" أو "عدم استقرار" بمعنى سلبي.
    الاسم والتفسير مصممين عمدًا يوصفوا ملاحظة محايدة، مش إنذار -- ده هيبقى
    مهم لما نوصل لطبقة الـ Expression (مراحل 6/7).

**التخزين:** Self-State مش متخزنة خالص -- بتتحسب "on the fly" كل مرة من
الـ Event Store + الحالة الحالية + التاريخ. مفيش drift ممكن يحصل بين حالة
مخزنة وحقيقة الأحداث، لأن مفيش حالة مخزنة أصلاً.
"""

from datetime import datetime, timedelta
from typing import Optional

from services import event_store, loan_service
from utils.time_utils import now_cairo

ENTITY_TYPE = "loan_installment"

UNRESOLVED_CONFLICT_HIGH_THRESHOLD = 3           # معتمد 2026-07-24
PENDING_OBLIGATION_CONCERN_THRESHOLD = 2          # معتمد 2026-07-24
FREQUENT_CORRECTIONS_THRESHOLD = 5                # معتمد 2026-07-24 (Stage 5.1)
TRACKING_STABILITY_WINDOW_DAYS = 30


def _parse_installment_date(date_str: str):
    """تحويل تاريخ القسط ('01/MM/YYYY') لـ date كائن قابل للمقارنة."""
    return datetime.strptime(date_str, "%d/%m/%Y").date()


def compute_unresolved_conflict() -> dict:
    """
    عدد الأقساط اللي آخر حدث conflict_status ليها لسه "pending" (مفيش
    "resolved" بعده). مبني حصريًا على أحداث attribute="conflict_status"
    (Stage 4 addendum) -- مسار منفصل تمامًا عن paid_status.
    """
    events = event_store.get_events_by_type_and_attribute(ENTITY_TYPE, "conflict_status")

    latest_per_entity = {}
    for e in events:
        entity_id = e.get("entity", {}).get("id")
        latest_per_entity[entity_id] = e  # الأحداث مرتّبة زمنيًا، فآخر واحد بيفضل هو الأحدث

    pending_entities = {
        entity_id: e for entity_id, e in latest_per_entity.items()
        if e.get("new_value") == "pending"
    }

    count = len(pending_entities)
    evidence_event_ids = [e["event_id"] for e in pending_entities.values()]

    if count >= UNRESOLVED_CONFLICT_HIGH_THRESHOLD:
        level = "high"
    elif count >= 1:
        level = "elevated"
    else:
        level = "none"

    return {
        "level": level,
        "count": count,
        "evidence_event_ids": evidence_event_ids,
        "explanation": (
            f"{count} قسط عليه تعارض متسجل 'pending' من غير حدث 'resolved' بعده"
            if count else "مفيش أي تعارض معلّق متسجل"
        ),
    }


def compute_pending_obligation_load() -> dict:
    """
    عدد الأقساط اللي تاريخ استحقاقها فات وهي لسه مش متسجلة كمدفوعة. مبني
    على جدول البرامج الثابت (بيانات معروفة، مش event) + حالة الدفع الحالية
    (نتاج متراكم للأحداث، evidence-based) + تاريخ اليوم.
    """
    today = now_cairo().date()
    paid_map = loan_service._get_paid_map()

    overdue_items = []
    for program in loan_service.PROGRAMS:
        for i, inst in enumerate(program["installments"]):
            due_date = _parse_installment_date(inst["date"])
            if due_date > today:
                continue
            is_paid = bool(paid_map.get(f"{program['id']}_{i}"))
            if is_paid:
                continue
            overdue_items.append({
                "identity_key": f"{program['id']}_{i}",
                "program": program["name"],
                "due_date": inst["date"],
                "amount": inst["amount"],
            })

    # الدليل: آخر حدث paid_status صريح لكل قسط متأخر (لو موجود). لو مفيش
    # أي حدث خالص، الدليل هو غياب أي تأكيد دفع + الجدول الثابت -- مش
    # هنخترع event_id مش موجود فعليًا.
    evidence_event_ids = []
    for item in overdue_items:
        events = [
            e for e in event_store.get_events_for_entity(ENTITY_TYPE, item["identity_key"])
            if e.get("attribute") == "paid_status"
        ]
        if events:
            evidence_event_ids.append(events[-1]["event_id"])

    count = len(overdue_items)
    if count >= PENDING_OBLIGATION_CONCERN_THRESHOLD:
        level = "concern"
    elif count >= 1:
        level = "light"
    else:
        level = "none"

    return {
        "level": level,
        "count": count,
        "evidence_event_ids": evidence_event_ids,
        "overdue_items": overdue_items,  # تفصيل إضافي مفيد -- مش جزء من العقد الأساسي
        "explanation": (
            f"{count} قسط فات ميعاد استحقاقه ولسه مش متسجل كمدفوع"
            if count else "مفيش أي قسط متأخر عن ميعاده"
        ),
    }


def compute_tracking_stability() -> dict:
    """
    معدل التصحيحات الصريحة (loan_update_installment) عبر كل الأقساط في
    آخر 30 يوم -- Stage 5.1.

    ملحوظة مقصودة: التصحيح الموثّق بسبب هو سلوك حوكمة *صحي* (بالظبط اللي
    Stage 2 مصمم يشجّعه بإجبار سبب صريح) -- مش دليل على مشكلة. البُعد ده
    بيوصف *معدل* موضوعي بس، والمستويات والتفسير مكتوبين عمدًا بصيغة محايدة
    (frequent_corrections) مش سلبية (unstable) -- عشان أي Expression مستقبلي
    يوصفه كملاحظة، مش إنذار.
    """
    events = event_store.get_events_by_type_and_attribute(ENTITY_TYPE, "paid_status")
    cutoff = now_cairo() - timedelta(days=TRACKING_STABILITY_WINDOW_DAYS)

    recent_corrections = [
        e for e in events
        if e.get("actor") == "loan_update_installment"
        and datetime.fromisoformat(e["occurred_at"]) >= cutoff
    ]

    count = len(recent_corrections)
    evidence_event_ids = [e["event_id"] for e in recent_corrections]
    level = "frequent_corrections" if count >= FREQUENT_CORRECTIONS_THRESHOLD else "none"

    return {
        "level": level,
        "count": count,
        "evidence_event_ids": evidence_event_ids,
        "explanation": (
            f"{count} تصحيح صريح موثّق بسبب في آخر {TRACKING_STABILITY_WINDOW_DAYS} يوم عبر كل الأقساط -- معدل تصحيح ملحوظ (ملاحظة موضوعية، مش مؤشر مشكلة بالضرورة)"
            if level == "frequent_corrections"
            else f"{count} تصحيح صريح في آخر {TRACKING_STABILITY_WINDOW_DAYS} يوم -- معدل عادي"
        ),
    }


def compute_self_state() -> dict:
    """Self-State الكاملة -- تجميع كل الأبعاد. بتتحسب فريش كل مرة، مش متخزنة."""
    return {
        "unresolved_conflict": compute_unresolved_conflict(),
        "pending_obligation_load": compute_pending_obligation_load(),
        "tracking_stability": compute_tracking_stability(),
        "computed_at": now_cairo().isoformat(),
    }
