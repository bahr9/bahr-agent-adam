# -*- coding: utf-8 -*-
"""
Tests First -- Self-Diagnosis (Architecture v2، Stage جديدة داخل الدستور المعتمد).

نطاق ضيق أول (زي tracking_stability بالظبط -- 5.1): بس نوعين حدث خام،
كل واحد مسجَّل عند حدود التنفيذ الحتمية (deterministic execution boundary)
الخاصة بيه -- مش مربوطين بملف واحد بعينه (services/self_diagnosis.py):
  1. validator_rejection -- كل مرة محاولة توليد تترفض من claim_validator
     (الحد الحتمي: services/companionship_layer.py).
  2. fallback_activation -- كل مرة الاتنين بيفشلوا وfallback بيتفعّل
     (نفس الحد الحتمي فوق).

tool_relevant_but_skipped مؤجَّل رسميًا (قرار أحمد 2026-07-24) -- مش
"خطوة تالية" عادية. اتفحص صراحة وطلع غير قابل للرصد حاليًا بالكامل تحت
عقد التنفيذ الموجود (تفاصيل كاملة في docstring services/self_diagnosis.py).

القاعدة الحاكمة: لا تشخيص من غير دليل قابل للتتبع -- كل استنتاج تشخيصي
(compute_fallback_count) لازم evidence_event_ids بتاعته ترجع لأحداث حقيقية
موجودة فعليًا في Event Store، مش عدّاد في الذاكرة.
"""

from services.firebase_service import init_firebase
from services import companionship_layer, event_store, self_diagnosis


MEANING_PACKET = {
    "referenced_facts": {"unresolved_conflict.count": 2},
    "fired_inferences": [{"rule_id": "unresolved_conflict_elevated", "text": "محتاج مراجعتك"}],
    "primary_focus": "unresolved_conflict",
    "confidence": "full",
    "allowed_topics": ["unresolved_conflict"],
}


def main():
    assert init_firebase(), "فشل الاتصال بـ Firebase"
    from services.firebase_service import firestore_db

    dimension = MEANING_PACKET["primary_focus"]
    pre_existing = event_store.get_events_for_entity("self_diagnosis", dimension)
    assert pre_existing == [], f"توقف احترازيًا -- لقيت {len(pre_existing)} حدث self_diagnosis سابق"

    baseline = self_diagnosis.compute_fallback_count()
    print(f"ℹ️ baseline fallback_count الحقيقي (كل الأبعاد): {baseline['count']}")

    original_call_llm = companionship_layer._call_llm
    created_event_ids = []

    try:
        # ============================================================
        # Part A: مسار سعيد (نجاح من أول مرة) -- صفر أحداث self_diagnosis
        # ============================================================
        def always_ok(mp, retry_feedback=None):
            return "عندك {unresolved_conflict.count} خلافات لسه معلّقة. {inference:unresolved_conflict_elevated}"

        companionship_layer._call_llm = always_ok
        result_a = companionship_layer.generate_message(MEANING_PACKET)
        assert result_a["source"] == "companionship"

        events_after_happy = event_store.get_events_for_entity("self_diagnosis", dimension)
        assert events_after_happy == [], f"المفروض صفر أحداث self_diagnosis في المسار السعيد، لقيت {events_after_happy}"
        print("✅ المسار السعيد: صفر أحداث self_diagnosis اتسجلت (زي ما المفروض -- مفيش عيب نشخّصه)")

        # ============================================================
        # Part B: رفض ثم fallback -- لازم يتسجل validator_rejection مرتين
        # (محاولة أولى وتانية) + fallback_activation مرة واحدة
        # ============================================================
        def always_bad(mp, retry_feedback=None):
            return "متقلقش، كله تمام."  # طمأنة غير مرخّصة -- هترفض في المحاولتين

        companionship_layer._call_llm = always_bad
        result_b = companionship_layer.generate_message(MEANING_PACKET)
        assert result_b["source"] == "fallback"

        events_after_fail = event_store.get_events_for_entity("self_diagnosis", dimension)
        created_event_ids.extend(e["event_id"] for e in events_after_fail)

        rejections = [e for e in events_after_fail if e["attribute"] == "validator_rejection"]
        fallbacks = [e for e in events_after_fail if e["attribute"] == "fallback_activation"]
        assert len(rejections) == 2, f"المفروض حدثين validator_rejection (محاولة 1 و2)، لقيت {len(rejections)}"
        assert len(fallbacks) == 1, f"المفروض حدث fallback_activation واحد، لقيت {len(fallbacks)}"
        print(f"✅ رفض + fallback: اتسجل {len(rejections)} validator_rejection + {len(fallbacks)} fallback_activation فعليًا في Event Store")

        # تأكيد إن الحدث فيه دليل قابل للرصد (مش مجرد فلاج فاضي)، وإن كل خطأ
        # محافظ على type بتاعه (deterministic/heuristic) -- مش رسالة نصية بس
        assert all("type" in e and "message" in e for e in rejections[0]["new_value"]), rejections[0]
        assert any("طمأنة" in e["message"] or "ادّعاء" in e["message"] for e in rejections[0]["new_value"]), rejections[0]
        print(f"✅ حدث validator_rejection فيه سبب الرفض الحقيقي (بنوعه محفوظ): {rejections[0]['new_value']}")

        # ============================================================
        # Part C: الاستنتاج التشخيصي -- لازم يرجع لأدلة حقيقية، مش عدّاد فاضي
        # ============================================================
        after_fallback = self_diagnosis.compute_fallback_count()
        assert after_fallback["count"] == baseline["count"] + 1
        assert len(after_fallback["evidence_event_ids"]) == after_fallback["count"]

        for eid in after_fallback["evidence_event_ids"]:
            real_event = event_store.get_event(eid)
            assert real_event is not None, f"evidence_event_id {eid} مش بيرجع لحدث حقيقي -- ده يخالف القاعدة الحاكمة"
            assert real_event["attribute"] == "fallback_activation"
        print(f"✅ compute_fallback_count: {after_fallback['count']} (زاد بـ 1 فعليًا)، كل evidence_event_ids بترجع لأحداث حقيقية متحقق منها")
        print(f"   التفسير: {after_fallback['explanation']}")

        # ============================================================
        # Part D: استنتاج تشخيصي جديد -- validator_rejection مجمّع بالنوع
        # (deterministic/heuristic)، بدون أي حكم سببي (طلب أحمد صراحة)
        # ============================================================
        baseline_diag = self_diagnosis.compute_validator_rejection_diagnosis()

        def mixed_type_rejection(mp, retry_feedback=None):
            # "5" رقم خام برّه أي slot -- deterministic. "متقلقش" ادّعاء
            # طمأنة حر -- heuristic. مفيش تقريب/نفي قاطع/تناقض حل في النص ده.
            return "عندك 5 مشاكل بس متقلقش."

        companionship_layer._call_llm = mixed_type_rejection
        result_d = companionship_layer.generate_message(MEANING_PACKET)
        assert result_d["source"] == "fallback"

        diag_after = self_diagnosis.compute_validator_rejection_diagnosis()
        assert diag_after["count"] == baseline_diag["count"] + 2, "المفروض حدثين رفض جداد (محاولة 1 و2)"

        det_delta = diag_after["by_type"].get("deterministic", 0) - baseline_diag["by_type"].get("deterministic", 0)
        heur_delta = diag_after["by_type"].get("heuristic", 0) - baseline_diag["by_type"].get("heuristic", 0)
        assert det_delta == 2, f"المفروض خطأ deterministic واحد في كل محاولة (2 إجمالي)، لقيت فرق {det_delta}"
        assert heur_delta == 2, f"المفروض خطأ heuristic واحد في كل محاولة (2 إجمالي)، لقيت فرق {heur_delta}"
        print(f"✅ compute_validator_rejection_diagnosis مجمّع بالنوع صح: by_type={diag_after['by_type']} (فرق deterministic={det_delta}, heuristic={heur_delta})")

        for eid in diag_after["evidence_event_ids"]:
            real_event = event_store.get_event(eid)
            assert real_event is not None, f"evidence_event_id {eid} مش بيرجع لحدث حقيقي"
            assert real_event["attribute"] == "validator_rejection"
        print(f"✅ كل evidence_event_ids ({len(diag_after['evidence_event_ids'])}) بترجع لأحداث validator_rejection حقيقية متحقق منها")

        # تفسير محايد -- صفر حكم سببي على "جودة تفكير" أو "استقرار" الموديل
        assert "سيء" not in diag_after["explanation"]
        assert "استقرار" not in diag_after["explanation"]
        assert "تفكير" not in diag_after["explanation"]
        print(f"   التفسير المحايد: {diag_after['explanation']}")

    finally:
        companionship_layer._call_llm = original_call_llm
        all_events = event_store.get_events_for_entity("self_diagnosis", dimension)
        for e in all_events:
            firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
        remaining = event_store.get_events_for_entity("self_diagnosis", dimension)
        assert remaining == []
        print(f"🧹 اتمسح {len(all_events)} حدث اختبار self_diagnosis")

    final = self_diagnosis.compute_fallback_count()
    assert final["count"] == baseline["count"]
    print(f"✅ fallback_count رجع لنفس الـbaseline: {final['count']}")

    print("\n✅✅✅ Self-Diagnosis (نطاق ضيق: validator_rejection + fallback_activation) شغال فعليًا، بدليل قابل للتتبع بالكامل")


if __name__ == "__main__":
    main()
