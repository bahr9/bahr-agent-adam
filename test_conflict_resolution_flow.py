# -*- coding: utf-8 -*-
"""
تحقق من Conflict Resolution Flow (Stage 4): loan_record_installment بتوقف
فعليًا ومتكتبش لما فيه تعارض، وloan_resolve_conflict هو المسار الوحيد
لتجاوز التوقف ده.

الثابت المحروس بدقة: الرفض مبيكتبش أي حدث paid_status ولا أي كتابة domain،
لكنه **بيسجّل** حدث conflict_status -- الرفض نفسه دليل لازم يفضل ليه أثر.

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
    assert original is False

    existing = event_store.get_events_for_entity("loan_installment", identity_key)
    assert existing == [], f"توقف احترازيًا -- لقيت {len(existing)} حدث سابق"

    # 1) تسجيل أول مرة -- المفروض يعدي عادي
    ok, msg, e1 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=999)
    assert ok and e1
    print(f"✅ أول تسجيل عدى عادي: {msg}")

    now_paid = loan_service.is_paid(program["id"], idx)
    assert now_paid is True

    # 2) محاولة تسجيل قيمة متعارضة عبر loan_record_installment -- المفروض توقف تمامًا
    ok2, msg2, e2 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, False, chat_id=999)
    assert ok2 is False, "❌ المفروض ترفض تكتب!"
    assert e2 is None, "❌ المفروض مفيش event_id -- يعني مفيش حدث اتسجل"
    assert "⚠️" in msg2 and "تعارض" in msg2
    print(f"✅ اترفضت الكتابة المتعارضة زي المتوقع: {msg2}")

    # 3) تأكيد: القيمة الفعلية متغيرتش (لسه True من الخطوة 1)
    still_true = loan_service.is_paid(program["id"], idx)
    assert still_true is True, "❌ القيمة اتغيرت رغم إن الكتابة المفروض تكون اترفضت!"
    print("✅ القيمة الفعلية متغيرتش -- الرفض كان حقيقي مش شكلي")

    # 4) تأكيد: الرفض مكتبش أي حدث paid_status جديد -- لسه حدث واحد بس.
    #    (تصحيح 2026-08-05: الاختبار كان بيعدّ **كل** الأحداث ويتوقع 1. لكن
    #    Stage 5 بيسجّل حدث conflict_status للرفض نفسه عن قصد، فالإجمالي 2.
    #    الثابت الحقيقي اللي لازم يتحرس هو "مفيش كتابة domain حصلت"، يعني
    #    مفيش paid_status جديد -- مش إن الرفض مالوش أثر خالص.)
    all_events = event_store.get_events_for_entity("loan_installment", identity_key)
    paid_events = [e for e in all_events if e.get("attribute") == "paid_status"]
    assert len(paid_events) == 1, f"❌ المفروض حدث paid_status واحد بس، لقيت {len(paid_events)}"
    print("✅ مفيش حدث paid_status اتسجل للمحاولة المرفوضة -- التوقف كان قبل أي كتابة domain")

    # والرفض نفسه لازم يسيب أثر -- وإلا مفيش دليل إن التعارض حصل أصلاً
    conflict_events = [e for e in all_events if e.get("attribute") == "conflict_status"]
    assert len(conflict_events) == 1, f"❌ المفروض حدث conflict_status واحد، لقيت {len(conflict_events)}"
    assert conflict_events[-1]["new_value"] == "pending", conflict_events[-1]
    print("✅ الرفض نفسه اتسجل كـ conflict_status=pending -- فيه دليل إن التعارض حصل")

    # 5) محاولة تسجيل نفس القيمة (True) تاني -- مش تعارض (duplicate)، المفروض تعدي عادي
    ok3, msg3, e3 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=999)
    assert ok3 and e3, "❌ نفس القيمة (duplicate) المفروض تعدي عادي مش تترفض"
    print(f"✅ إعادة تسجيل نفس القيمة (duplicate) عدت عادي زي المتوقع: {msg3}")

    # 6) حل التعارض فعليًا عبر loan_resolve_conflict بسبب -- ده المسار الوحيد للتغيير الفعلي
    ok4, msg4, e4 = loan_commands.loan_resolve_conflict(
        PROGRAM, MONTH_KEY, False, reason="استرجاع الحالة الأصلية بعد تحقق Stage 4", chat_id=999
    )
    assert ok4 and e4
    print(f"✅ loan_resolve_conflict كتب فعليًا: {msg4}")

    final = loan_service.is_paid(program["id"], idx)
    assert final == original, "❌ القيمة النهائية مرجعتش لأصلها"
    print("✅ القيمة النهائية رجعت لنفس الحالة الأصلية")

    c_final = loan_conflict_observer.classify_installment(program["id"], idx)
    assert c_final["classification"] == "update"
    print(f"✅ الحدث الأخير (resolve_conflict) اتصنف 'update' زي المتوقع")

    # تنظيف
    from services.firebase_service import firestore_db
    all_events = event_store.get_events_for_entity("loan_installment", identity_key)
    for e in all_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    remaining = event_store.get_events_for_entity("loan_installment", identity_key)
    assert remaining == []
    print(f"🧹 اتمسح {len(all_events)} حدث اختبار -- الـ Store رجع نضيف")

    print("\n✅✅✅ Stage 4 verification: التوقف الفعلي عند التعارض شغال، وloan_resolve_conflict هو المسار الوحيد للتجاوز")


if __name__ == "__main__":
    main()
