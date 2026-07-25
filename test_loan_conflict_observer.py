# -*- coding: utf-8 -*-
"""
تحقق فعلي من Loan Conflict Observer (Stage 3) -- نفس القسط الآمن اللي
اتستخدم في Stage 2 (Credit Agricole، آخر قسط، 01/06/2032). بيمشّي على
كل الحالات الأربعة (new/duplicate/update/conflict) بأحداث حقيقية، وبيرجّع
القيمة لحالتها الأصلية في الآخر، وبينضف كل أحداث الاختبار.
"""

from services.firebase_service import init_firebase
from services import loan_service, loan_commands, event_store, loan_conflict_observer

PROGRAM = "Credit Agricole"
MONTH_KEY = "01/06/2032"


def main():
    assert init_firebase(), "فشل الاتصال بـ Firebase"

    program = loan_service._find_program(PROGRAM)
    idx = len(program["installments"]) - 1
    identity_key = f"{program['id']}_{idx}"

    original = loan_service.is_paid(program["id"], idx)
    print(f"الحالة الأصلية: {original} | entity_id={identity_key}")
    assert original is False, "توقف احترازيًا -- المفروض يكون False"

    existing = event_store.get_events_for_entity("loan_installment", identity_key)
    assert existing == [], f"مفيش المفروض يكون فيه أحداث سابقة، لقيت {len(existing)} -- توقف احترازيًا"

    # 0) مفيش تاريخ خالص -> classify يرجع None
    c0 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c0 is None
    print("✅ classify_installment رجّع None لما مفيش أي تاريخ")

    # 1) أول تسجيل -> "new"
    ok, msg, e1 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=999)
    assert ok
    c1 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c1["classification"] == "new", c1
    print(f"✅ أول حدث اتصنف 'new': {c1['explanation']}")

    # 2) نفس القيمة تاني -> "duplicate"
    ok, msg, e2 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=999)
    assert ok
    c2 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c2["classification"] == "duplicate", c2
    print(f"✅ نفس القيمة اتصنفت 'duplicate': {c2['explanation']}")

    # 3) قيمة مختلفة عبر loan_record_installment تاني (مش update) -> "conflict"
    ok, msg3, e3 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, False, chat_id=999)
    assert ok
    assert "⚠️" in msg3, "المفروض الرسالة تتضمن ملحوظة التعارض"
    c3 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c3["classification"] == "conflict", c3
    print(f"✅ قيمة متضاربة من غير تصحيح اتصنفت 'conflict': {c3['explanation']}")
    print(f"   الرسالة الراجعة فعلاً فيها الملحوظة: {msg3.splitlines()[-1]}")

    # 4) تصحيح صريح بسبب -> "update"
    ok, msg4, e4 = loan_commands.loan_update_installment(
        PROGRAM, MONTH_KEY, True, reason="تصحيح تجريبي -- Stage 3 verification", chat_id=999
    )
    assert ok
    c4 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c4["classification"] == "update", c4
    print(f"✅ تصحيح صريح اتصنف 'update': {c4['explanation']}")

    # 5) حل تعارض يدوي -> "update" برضه (قناة صريحة موثقة)، وبيرجع القيمة لأصلها (False)
    ok, msg5, e5 = loan_commands.loan_resolve_conflict(
        PROGRAM, MONTH_KEY, False, reason="استرجاع الحالة الأصلية بعد تحقق Stage 3", chat_id=999
    )
    assert ok
    c5 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c5["classification"] == "update", c5
    print(f"✅ حل تعارض يدوي اتصنف 'update': {c5['explanation']}")

    final = loan_service.is_paid(program["id"], idx)
    assert final == original, "❌ القيمة النهائية مرجعتش لأصلها"
    print("✅ القيمة النهائية رجعت لنفس الحالة الأصلية")

    # تنظيف -- مسح كل أحداث الاختبار
    from services.firebase_service import firestore_db
    all_events = event_store.get_events_for_entity("loan_installment", identity_key)
    for e in all_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    remaining = event_store.get_events_for_entity("loan_installment", identity_key)
    assert remaining == []
    print(f"🧹 اتمسح {len(all_events)} حدث اختبار -- الـ Store رجع نضيف")

    print("\n✅✅✅ Stage 3 verification: كل التصنيفات الأربعة (new/duplicate/update/conflict) شغالة صح")


if __name__ == "__main__":
    main()
