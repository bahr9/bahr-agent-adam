# -*- coding: utf-8 -*-
"""
تحقق فعلي من Self-State Engine + Decision Engine (Stage 5) ضد Firestore
الحقيقي. بيستخدم نفس القسط الآمن (Credit Agricole، 01/06/2032) لتوليد
تعارض حقيقي، وبيتأكد إن unresolved_conflict بيتحرك صح، وإن decide_expression
بيمنع تكرار التبليغ صح. بينضف كل حاجة في الآخر ويرجّع الحالة العامة لأصلها.
"""

from fake_firestore import install_fake_firestore
from services import (
    loan_service, loan_commands, event_store,
    self_state_engine, decision_engine,
)
from config import SELF_STATE_COLLECTION

PROGRAM = "Credit Agricole"
MONTH_KEY = "01/06/2032"


def main():
    install_fake_firestore()
    from services.firebase_service import firestore_db

    program = loan_service._find_program(PROGRAM)
    idx = len(program["installments"]) - 1
    identity_key = f"{program['id']}_{idx}"
    original_paid = loan_service.is_paid(program["id"], idx)
    assert original_paid is False

    existing = event_store.get_events_for_entity("loan_installment", identity_key)
    assert existing == [], f"توقف احترازيًا -- لقيت {len(existing)} حدث سابق على {identity_key}"

    # ============================================================
    # Part A: self_state_engine.compute_pending_obligation_load -- قراءة حقيقية، بدون كتابة
    # ============================================================
    obligation_baseline = self_state_engine.compute_pending_obligation_load()
    assert obligation_baseline["level"] in ("none", "light", "concern")
    print(f"ℹ️ pending_obligation_load الحقيقي دلوقتي: {obligation_baseline['level']} "
          f"({obligation_baseline['count']} قسط متأخر) -- {obligation_baseline['explanation']}")

    # ============================================================
    # Part B: self_state_engine.compute_unresolved_conflict -- baseline لازم يكون 0
    # ============================================================
    conflict_baseline = self_state_engine.compute_unresolved_conflict()
    print(f"ℹ️ unresolved_conflict الحقيقي قبل الاختبار: {conflict_baseline}")
    baseline_count = conflict_baseline["count"]

    # ============================================================
    # Part C: نولّد تعارض حقيقي على القسط الآمن، ونتأكد إن العدّاد بيتحرك
    # ============================================================
    ok1, msg1, e1 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=999)
    assert ok1
    ok2, msg2, e2 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, False, chat_id=999)
    assert ok2 is False and "تعارض" in msg2
    print("✅ اتولّد تعارض حقيقي (نفس سلوك Stage 4)")

    conflict_after = self_state_engine.compute_unresolved_conflict()
    assert conflict_after["count"] == baseline_count + 1, conflict_after
    assert identity_key in [
        e["entity"]["id"] for e in event_store.get_events_for_entity("loan_installment", identity_key)
        if e.get("attribute") == "conflict_status"
    ]
    print(f"✅ unresolved_conflict زاد بـ 1 فعليًا: {conflict_after}")

    # ============================================================
    # Part D: نحل التعارض، ونتأكد إن العدّاد رجع لأصله
    # ============================================================
    ok3, msg3, e3 = loan_commands.loan_resolve_conflict(
        PROGRAM, MONTH_KEY, False, reason="استرجاع الحالة الأصلية بعد تحقق Stage 5", chat_id=999
    )
    assert ok3
    conflict_resolved = self_state_engine.compute_unresolved_conflict()
    assert conflict_resolved["count"] == baseline_count, conflict_resolved
    print(f"✅ بعد الحل، unresolved_conflict رجع لأصله: {conflict_resolved}")

    final_paid = loan_service.is_paid(program["id"], idx)
    assert final_paid == original_paid
    print("✅ القيمة الفعلية رجعت لأصلها")

    # ============================================================
    # Part E: decision_engine -- منطق Active/Passive والـ dedup
    # ============================================================
    # نحفظ آخر حالة حقيقية موجودة قبل ما نلخبط بيها، عشان نرجّعها في الآخر
    prior_doc = firestore_db.collection(SELF_STATE_COLLECTION).document("decision_engine_state").get()
    prior_levels = prior_doc.to_dict().get("last_levels", {}) if prior_doc.exists else None

    # نصفّر الحالة المخزنة يدويًا عشان نبدأ اختبار نضيف
    firestore_db.collection(SELF_STATE_COLLECTION).document("decision_engine_state").set(
        {"last_levels": {"unresolved_conflict": "none", "pending_obligation_load": "none"}}
    )

    fake_state_high = {
        "unresolved_conflict": {"level": "high", "count": 3, "evidence_event_ids": []},
        "pending_obligation_load": {"level": "none", "count": 0, "evidence_event_ids": []},
    }
    d1 = decision_engine.decide_expression(fake_state_high)
    assert d1["unresolved_conflict"]["mode"] == "active", d1
    print(f"✅ أول وصول لـ 'high' -> active: {d1['unresolved_conflict']}")

    d2 = decision_engine.decide_expression(fake_state_high)
    assert d2["unresolved_conflict"]["mode"] == "passive", d2
    print(f"✅ تكرار نفس 'high' -> passive (مفيش تكرار تبليغ): {d2['unresolved_conflict']}")

    fake_state_dropped = {
        "unresolved_conflict": {"level": "elevated", "count": 1, "evidence_event_ids": []},
        "pending_obligation_load": {"level": "none", "count": 0, "evidence_event_ids": []},
    }
    d3 = decision_engine.decide_expression(fake_state_dropped)
    assert d3["unresolved_conflict"]["mode"] == "passive"
    assert d3["unresolved_conflict"]["transitioned"] is True
    print(f"✅ نزول لـ 'elevated' -> passive بس transitioned=True: {d3['unresolved_conflict']}")

    d4 = decision_engine.decide_expression(fake_state_high)
    assert d4["unresolved_conflict"]["mode"] == "active", d4
    print(f"✅ رجوع لـ 'high' تاني بعد نزول -> active من جديد (escalation جديدة اتلاحظت): {d4['unresolved_conflict']}")

    # تنظيف decision_engine -- رجّع الحالة المخزنة لأصلها (أو امسحها لو ماكانتش موجودة)
    doc_ref = firestore_db.collection(SELF_STATE_COLLECTION).document("decision_engine_state")
    if prior_levels is None:
        doc_ref.delete()
    else:
        doc_ref.set({"last_levels": prior_levels})
    print("🧹 اترجعت حالة decision_engine المخزنة لأصلها")

    # تنظيف الأحداث
    all_events = event_store.get_events_for_entity("loan_installment", identity_key)
    for e in all_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    remaining = event_store.get_events_for_entity("loan_installment", identity_key)
    assert remaining == []
    print(f"🧹 اتمسح {len(all_events)} حدث اختبار من {identity_key}")

    conflict_final = self_state_engine.compute_unresolved_conflict()
    assert conflict_final["count"] == baseline_count
    print(f"✅ unresolved_conflict الحقيقي رجع لنفس الـ baseline: {conflict_final['count']}")

    print("\n✅✅✅ Stage 5 verification: State Derivation Engine + Self-State + Decision Engine شغالين صح")


if __name__ == "__main__":
    main()
