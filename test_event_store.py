# -*- coding: utf-8 -*-
"""
تحقق فعلي من Event Store (Stage 1) -- بيكتب/يقرأ حدث تجريبي حقيقي في Firestore
ثم يمسحه. مش unit test framework، مجرد سكريبت تحقق يدوي زي test_memory.py.
"""

from fake_firestore import install_fake_firestore
from services import event_store


def main():
    install_fake_firestore()

    # 1) رفض حدث ناقص الحقول الإجبارية
    for kwargs in [
        dict(entity_type="", entity_id="x", attribute="y"),
        dict(entity_type="x", entity_id="", attribute="y"),
        dict(entity_type="x", entity_id="y", attribute=""),
    ]:
        try:
            event_store.record_event(new_value=1, **kwargs)
            raise SystemExit(f"❌ فشل: كان المفروض يترفض -- {kwargs}")
        except event_store.InvalidEventError:
            print(f"✅ اترفض صح: {kwargs}")

    # 2) تسجيل حدث حقيقي
    event_id = event_store.record_event(
        entity_type="test",
        entity_id="stage1_verification",
        attribute="smoke_test",
        previous_value=None,
        new_value="ok",
        source="manual",
        actor="test_event_store.py",
        raw_context={"note": "Stage 1 verification run"},
    )
    print(f"✅ اتسجل الحدث: {event_id}")

    # 3) قراءته تاني بـ get_event
    fetched = event_store.get_event(event_id)
    assert fetched is not None, "❌ مش لاقي الحدث بعد التسجيل"
    assert fetched["entity"] == {"type": "test", "id": "stage1_verification"}
    assert fetched["attribute"] == "smoke_test"
    assert fetched["new_value"] == "ok"
    assert fetched["entity_key"] == "test:stage1_verification"
    print("✅ get_event رجّع نفس البيانات المتوقعة")

    # 4) get_events_for_entity
    events = event_store.get_events_for_entity("test", "stage1_verification")
    assert any(e["event_id"] == event_id for e in events), "❌ الحدث مش في نتيجة get_events_for_entity"
    print(f"✅ get_events_for_entity رجّع {len(events)} حدث ولقى الحدث اللي اتسجل")

    # 5) تنظيف -- مسح الحدث التجريبي (مرة واحدة، يدوي، مش جزء من الـ API)
    from services.firebase_service import firestore_db
    firestore_db.collection(event_store.EVENTS_COLLECTION).document(event_id).delete()
    assert event_store.get_event(event_id) is None
    print("🧹 اتمسح الحدث التجريبي بعد التأكد")

    print("\n✅✅✅ Stage 1 verification: كله شغال")


if __name__ == "__main__":
    main()
