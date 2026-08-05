# -*- coding: utf-8 -*-
"""
تحقق من tracking_stability (Stage 5.1): 5 تصحيحات (loan_update_installment)
ويتأكد إن العتبة (5) بتشتغل صح والتفسير محايد مش سلبي.

بيشتغل على fake_firestore -- صفر شبكة، وكان بيكتب على الإنتاج قبل كده.
"""

from fake_firestore import install_fake_firestore
from services import loan_service, loan_commands, event_store, self_state_engine

PROGRAM = "Credit Agricole"
MONTH_KEY = "01/06/2032"


def main():
    install_fake_firestore()

    program = loan_service._find_program(PROGRAM)
    idx = len(program["installments"]) - 1
    identity_key = f"{program['id']}_{idx}"
    original_paid = loan_service.is_paid(program["id"], idx)
    assert original_paid is False

    existing = event_store.get_events_for_entity("loan_installment", identity_key)
    assert existing == [], f"توقف احترازيًا -- لقيت {len(existing)} حدث سابق"

    baseline = self_state_engine.compute_tracking_stability()
    print(f"ℹ️ tracking_stability baseline: {baseline}")
    assert baseline["count"] == 0 and baseline["level"] == "none", baseline

    # 4 تصحيحات -- لسه تحت العتبة (5)
    for i in range(4):
        ok, msg, eid = loan_commands.loan_update_installment(
            PROGRAM, MONTH_KEY, paid=(i % 2 == 0), reason=f"تصحيح تجريبي رقم {i+1} -- Stage 5.1 verification"
        )
        assert ok, msg

    under_threshold = self_state_engine.compute_tracking_stability()
    assert under_threshold["count"] == 4, under_threshold
    assert under_threshold["level"] == "none", under_threshold
    print(f"✅ بعد 4 تصحيحات: {under_threshold} -- لسه 'none' زي المتوقع (تحت عتبة 5)")

    # التصحيح الخامس -- المفروض يعدّي العتبة
    ok, msg, eid = loan_commands.loan_update_installment(
        PROGRAM, MONTH_KEY, paid=True, reason="تصحيح تجريبي رقم 5 -- Stage 5.1 verification"
    )
    assert ok, msg

    at_threshold = self_state_engine.compute_tracking_stability()
    assert at_threshold["count"] == 5, at_threshold
    assert at_threshold["level"] == "frequent_corrections", at_threshold
    assert len(at_threshold["evidence_event_ids"]) == 5
    assert "مؤشر مشكلة" not in at_threshold["explanation"] or "مش مؤشر مشكلة" in at_threshold["explanation"]
    print(f"✅ بعد 5 تصحيحات: {at_threshold}")
    print(f"   التفسير محايد: {at_threshold['explanation']}")

    # تأكيد إن compute_self_state() بقى فيه الثلاث أبعاد كلهم
    full_state = self_state_engine.compute_self_state()
    assert set(["unresolved_conflict", "pending_obligation_load", "tracking_stability"]).issubset(full_state.keys())
    print("✅ compute_self_state() فيه الثلاث أبعاد كلهم دلوقتي")

    # تأكيد إن decision_engine ماشافش tracking_stability كـ Active-eligible
    from services import decision_engine
    assert "tracking_stability" not in decision_engine.HIGHEST_TIER
    print("✅ tracking_stability مش موجودة في HIGHEST_TIER -- مش هتبقى Active أبدًا زي ما اتفقنا")

    # تنظيف -- رجّع القيمة لأصلها وامسح كل الأحداث
    from services.firebase_service import firestore_db
    ok, msg, eid = loan_commands.loan_update_installment(
        PROGRAM, MONTH_KEY, paid=original_paid, reason="استرجاع الحالة الأصلية بعد تحقق Stage 5.1"
    )
    assert ok

    all_events = event_store.get_events_for_entity("loan_installment", identity_key)
    for e in all_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    remaining = event_store.get_events_for_entity("loan_installment", identity_key)
    assert remaining == []
    print(f"🧹 اتمسح {len(all_events)} حدث اختبار")

    final_paid = loan_service.is_paid(program["id"], idx)
    assert final_paid == original_paid
    print("✅ القيمة الفعلية رجعت لأصلها")

    final_state = self_state_engine.compute_tracking_stability()
    assert final_state["count"] == 0 and final_state["level"] == "none"
    print(f"✅ tracking_stability رجع لنفس الـ baseline: {final_state}")

    print("\n✅✅✅ Stage 5.1 verification: tracking_stability شغالة صح بالعتبة 5 والتفسير المحايد")


if __name__ == "__main__":
    main()
