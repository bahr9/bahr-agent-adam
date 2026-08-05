# -*- coding: utf-8 -*-
"""
تحقق من Loan Conflict Observer (Stage 3): كل الحالات الأربعة
(new/duplicate/update/conflict).

ملحوظة معمارية: تصنيف "conflict" بقى غير قابل للإنتاج عبر الـ command API
بعد Stage 4 -- loan_record_installment بترفض الكتابة المتعارضة أصلاً. يعني
الفرع ده في الملاحِظ بيتفعّل بس على أحداث قديمة اتسجلت قبل Stage 4. الاختبار
بيسجّل حدث بنفس الشكل ده مباشرة عشان يتحقق من عقد الملاحِظ.

بيشتغل على fake_firestore -- صفر شبكة.
"""

from fake_firestore import install_fake_firestore
from services import loan_service, loan_commands, event_store, loan_conflict_observer

PROGRAM = "Credit Agricole"
MONTH_KEY = "01/06/2032"


def main():
    install_fake_firestore()

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

    # 3أ) نفس الطلب المتعارض عبر loan_record_installment -- Stage 4 بيرفضه
    #     (تصحيح 2026-08-05: الاختبار ده اتكتب في Stage 3 وكان بيتوقع
    #     `ok is True`، لأن ساعتها الملاحِظ كان بيصنّف بس والكتابة كانت
    #     بتعدّي. Stage 4 خلّى الكتابة تتوقف تمامًا، والاختبار مااتحدّثش.)
    ok, msg3, e3 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, False, chat_id=999)
    assert ok is False, "Stage 4 المفروض يرفض الكتابة المتعارضة"
    assert e3 is None, "مفيش حدث paid_status المفروض يتسجل للطلب المرفوض"
    assert "⚠️" in msg3 and "تعارض" in msg3
    print(f"✅ الطلب المتعارض اترفض (Stage 4): {msg3.splitlines()[0]}")

    # 3ب) التصنيف "conflict" نفسه: بقى غير قابل للإنتاج عبر الـ command API
    #     بعد Stage 4، فبنسجّل حدث paid_status مباشرة بنفس شكل الأحداث
    #     القديمة (actor=loan_record_installment) عشان نتحقق من عقد الملاحِظ.
    event_store.record_event(
        entity_type="loan_installment", entity_id=identity_key,
        attribute="paid_status", new_value=False, previous_value=True,
        source="llm_tool", actor="loan_record_installment",
        raw_context={"note": "حدث قديم قبل Stage 4 -- محاكاة للتحقق من التصنيف"},
    )
    c3 = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c3["classification"] == "conflict", c3
    print(f"✅ حدث متعارض قديم اتصنف 'conflict': {c3['explanation'][:80]}...")
    # آخر قيمة متسجلة دلوقتي False -- فالخطوة الجاية (تصحيح لـ True) بتبقى
    # تغيير حقيقي، وده اللي بيخلي التصنيف "update" مش "duplicate"

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
