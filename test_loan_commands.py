# -*- coding: utf-8 -*-
"""
تحقق من Loan Command API (Stage 2): تسجيل -> تحقق -> رجوع للحالة الأصلية.

قاعدة الاختبارات (2026-08-05): الاختبار ده كان بيكتب حدثين حقيقيين في
adam_events عند كل تشغيلة، والحدثين دول كانوا بيمنعوا تلات اختبارات تانية
من الشغل أصلاً (كانوا بيشترطوا سجل نضيف على نفس الكيان). دلوقتي بيشتغل على
fake_firestore بالكامل -- صفر شبكة وصفر أثر على الإنتاج.
"""

from fake_firestore import install_fake_firestore
from services import loan_service, loan_commands, event_store

PROGRAM = "Credit Agricole"
MONTH_KEY = "01/06/2032"  # آخر قسط -- بعيد جدًا وآمن للاختبار


def main():
    install_fake_firestore()

    program = loan_service._find_program(PROGRAM)
    idx = len(program["installments"]) - 1
    assert program["installments"][idx]["date"] == MONTH_KEY, "القسط المستهدف مش زي المتوقع -- توقف احترازيًا"

    original = loan_service.is_paid(program["id"], idx)
    print(f"الحالة الأصلية لقسط {PROGRAM} ({MONTH_KEY}): {'مدفوع' if original else 'غير مدفوع'}")
    assert original is False, "القسط ده المفروض يكون False -- توقف احترازيًا، مش هينفذ التبديل"

    # 1) رفض بدون program_name صحيح
    ok, msg, event_id = loan_commands.loan_record_installment("برنامج مش موجود خالص", None, True)
    assert ok is False and event_id is None
    print(f"✅ اترفض صح لبرنامج غير موجود: {msg}")

    # 2) رفض loan_update_installment من غير سبب
    ok, msg, event_id = loan_commands.loan_update_installment(PROGRAM, MONTH_KEY, True, reason="")
    assert ok is False and event_id is None
    print(f"✅ اترفض صح -- تعديل من غير سبب: {msg}")

    # 3) تسجيل حقيقي -- تبديل القيمة (False -> True)
    ok, msg, event_id = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=999)
    assert ok and event_id
    print(f"✅ اتسجل: {msg} | event_id={event_id}")

    now_paid = loan_service.is_paid(program["id"], idx)
    assert now_paid is True, "الكتابة الفعلية مطلعتش القيمة الجديدة"
    print("✅ القيمة الفعلية في Firestore اتغيرت فعلاً لـ True")

    event = event_store.get_event(event_id)
    assert event["entity"] == {"type": "loan_installment", "id": f"{program['id']}_{idx}"}
    assert event["attribute"] == "paid_status"
    assert event["previous_value"] is False and event["new_value"] is True
    assert event["source"] == "llm_tool" and event["actor"] == "loan_record_installment"
    print("✅ الحدث المسجل فيه كل الحقول المتوقعة (entity, attribute, previous/new value, source, actor)")

    # 4) الرجوع لنفس الحالة الأصلية (True -> False) عبر loan_update_installment (تصحيح، بسبب)
    ok, msg2, event_id2 = loan_commands.loan_update_installment(
        PROGRAM, MONTH_KEY, False, reason="استرجاع الحالة الأصلية بعد تحقق Stage 2", chat_id=999
    )
    assert ok and event_id2
    print(f"✅ اترجع: {msg2} | event_id={event_id2}")

    final = loan_service.is_paid(program["id"], idx)
    assert final == original, "❌ القيمة النهائية مرجعتش لأصلها"
    print("✅ القيمة النهائية رجعت لنفس الحالة الأصلية (غير مدفوع)")

    event2 = event_store.get_event(event_id2)
    assert event2["previous_value"] is True and event2["new_value"] is False
    assert event2["metadata"].get("reason") == "استرجاع الحالة الأصلية بعد تحقق Stage 2"
    assert event2["metadata"].get("is_correction") is True
    print("✅ حدث التصحيح فيه السبب وعلامة is_correction صح")

    # 5) تأكيد إن loan_mark_paid القديمة مش موجودة خالص في الـ dispatch
    from services.claude_service import TOOLS
    tool_names = [t["name"] for t in TOOLS]
    assert "loan_mark_paid" not in tool_names, "❌ loan_mark_paid لسه موجودة في TOOLS!"
    assert "loan_record_installment" in tool_names
    assert "loan_update_installment" in tool_names
    assert "loan_resolve_conflict" in tool_names
    print("✅ loan_mark_paid اتشالت نهائيًا من TOOLS، والثلاث أدوات الجديدة موجودة")

    print("\n✅✅✅ Stage 2 verification: كله شغال، والقسط رجع لحالته الأصلية بالظبط")
    print("\nكل ده حصل على fake_firestore في الذاكرة -- ولا حرف اتكتب في Firestore الحقيقي.")


if __name__ == "__main__":
    main()
