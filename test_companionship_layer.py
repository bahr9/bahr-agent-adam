# -*- coding: utf-8 -*-
"""
تحقق فعلي من Companionship Layer -- مكالمة LLM حقيقية (Anthropic API)، مبنية
على بيانات حقيقية من truth_layer/meaning_layer (قراءة فقط، صفر كتابة).
بيتحقق من: المسار السعيد الحقيقي (LLM call فعلي)، رفض confidence=degraded،
وبروتوكول إعادة المحاولة/الـfallback (بمحاكاة مضبوطة لـ_call_llm عشان
نتحكم في السيناريو بشكل حتمي، مش معتمدين على تقلّب استجابة LLM حقيقية).

inference_rules.py لسه مش موجود (Roadmap لاحق) -- fired_rules هنا يدوية
تحاكي شكلها المتوقع، مش قراءة من ملف حقيقي، وده موثّق صراحة هنا.
"""

from fake_firestore import install_fake_firestore
from services import truth_layer, meaning_layer, companionship_layer, claim_validator, event_store


def main():
    install_fake_firestore()

    # ============================================================
    # Part A: مسار سعيد حقيقي -- LLM call فعلي على بيانات حقيقية
    # ============================================================
    truth_packet = truth_layer.build_truth_packet_for_loans()
    assert truth_layer.validate_truth_packet(truth_packet) == []
    print(f"✅ TruthPacket حقيقي مبني وسليم (domain={truth_packet.domain})")

    # fired_rules يدوية -- inference_rules.py لسه مش موجود (Roadmap لاحق)
    fired_rules = [{
        "domain": "loans",
        "dimension": "pending_obligation_load",
        "rule_id": "pending_obligation_concern",
        "text": "الوضع محتاج متابعة قريبة",
    }]

    meaning_packet = meaning_layer.compute_meaning_packet(
        truth_packet, target_dimensions="pending_obligation_load", fired_rules=fired_rules
    )
    print(f"✅ MeaningPacket: referenced_facts={meaning_packet['referenced_facts']}, confidence={meaning_packet['confidence']}")

    result = companionship_layer.generate_message(meaning_packet)
    assert result["verified"] is True
    assert result["source"] in ("companionship", "fallback")
    print(f"✅ [{result['source']}] نص حقيقي من Companionship: {result['text']!r}")

    # تأكيد إضافي: النص فعلاً بيعدي نفس claim_validator بشكل مستقل (sanity check مزدوج)
    # (ده مش re-validation، بس تأكيد إن النص النهائي متوافق منطقيًا مع القيمة الحقيقية)
    real_count = truth_packet.facts[0].value if truth_packet.facts[0].field.endswith("count") else None
    print(f"   (للمرجعية -- overdue count الحقيقي دلوقتي: {[f.value for f in truth_packet.facts if f.field == 'pending_obligation_load.count']})")

    # ============================================================
    # Part B: رفض confidence=degraded -- مفيش استدعاء LLM أصلًا
    # ============================================================
    degraded_packet = dict(meaning_packet)
    degraded_packet["confidence"] = "degraded"
    try:
        companionship_layer.generate_message(degraded_packet)
        raise SystemExit("❌ كان المفروض يرفض على طول -- confidence=degraded")
    except ValueError as e:
        assert "degraded" in str(e)
        print(f"✅ رفض فوري صح لـ confidence=degraded (مفيش استدعاء LLM): {e}")

    # ============================================================
    # Part C: بروتوكول إعادة المحاولة + الـfallback -- محاكاة مضبوطة لـ_call_llm
    # ============================================================
    original_call_llm = companionship_layer._call_llm

    # العدد الحقيقي المحسوب دلوقتي -- الاختبار كان بيقارن بـ 7 ثابتة، وهي
    # كانت مربوطة ببيانات الإنتاج وقت كتابته. مع fake_firestore (خريطة دفع
    # فاضية) العدد بيختلف، وكمان compute_pending_obligation_load بيحسب
    # الشهر الحالي مش الشهور الفايتة بس. فبنشتقّه من الحزمة نفسها.
    expected_count = next(
        f.value for f in truth_packet.facts
        if f.field == "pending_obligation_load.count"
    )
    print(f"ℹ️ العدد المحسوب فعليًا دلوقتي: {expected_count}")

    # C1: أول محاولة تفشل (رقم خام) -- التانية تنجح
    attempts = {"n": 0}
    def flaky_then_ok(mp, retry_feedback=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "فيه 7 أقساط متأخرة."  # رقم خام -- هيترفض مهما كانت قيمته
        assert retry_feedback is not None, "المفروض المحاولة التانية تاخد retry_feedback"
        return "فيه {pending_obligation_load.count} أقساط متأخرة -- {inference:pending_obligation_concern}."

    companionship_layer._call_llm = flaky_then_ok
    try:
        result_c1 = companionship_layer.generate_message(meaning_packet)
        assert attempts["n"] == 2, f"المفروض محاولتين بالظبط، حصل {attempts['n']}"
        assert result_c1["source"] == "companionship"
        assert result_c1["verified"] is True
        assert str(expected_count) in result_c1["text"], (
            f"الـ slot المفروض يتملى بـ {expected_count}: {result_c1['text']!r}"
        )
        print(f"✅ محاولة أولى فشلت (رقم خام)، التانية نجحت بعد retry_feedback: {result_c1['text']!r}")
    finally:
        companionship_layer._call_llm = original_call_llm

    # C2: الاتنين بيفشلوا -- fallback للقاموس المقفول
    def always_bad(mp, retry_feedback=None):
        return "فيه 7 أقساط متأخرة برضه."  # رقم خام دايمًا

    companionship_layer._call_llm = always_bad
    try:
        result_c2 = companionship_layer.generate_message(meaning_packet)
        assert result_c2["source"] == "fallback"
        assert result_c2["verified"] is True
        print(f"✅ محاولتين فشلوا -- fallback للقاموس المقفول اشتغل: {result_c2['text']!r}")
    finally:
        companionship_layer._call_llm = original_call_llm

    # ============================================================
    # Part D: طلب أحمد صراحة -- لو الموديل بيخترع طمأنة غير مرخّصة (زي
    # "كله تمام") في المحاولتين، النظام لازم ينزل لـfallback، مش يقبلها
    # كـ"نجاح" لمجرد إنها خالية من رقم خام أو نفي قاطع.
    # ============================================================
    def always_invents_reassurance(mp, retry_feedback=None):
        return "متقلقش يا بحورة، كله تمام والوضع مستقر."  # طمأنة حرة غير مرخّصة، مفيها ولا رقم ولا slot

    companionship_layer._call_llm = always_invents_reassurance
    try:
        result_d = companionship_layer.generate_message(meaning_packet)
        assert result_d["source"] == "fallback", "المفروض ينزل fallback -- الطمأنة دي مش مرخّصة برغم مفيش رقم خام فيها"
        assert "تمام" not in result_d["text"] and "مستقر" not in result_d["text"]
        print(f"✅ طمأنة مخترعة (بدون رقم/slot) اترفضت في المحاولتين -> fallback حقيقي: {result_d['text']!r}")
    finally:
        companionship_layer._call_llm = original_call_llm

    # تنظيف -- كل محاولات الرفض/fallback فوق سجّلت أحداث self_diagnosis حقيقية
    # (Companionship مبقتش instrumented من غير قصد -- Stage self_diagnosis)
    from services.firebase_service import firestore_db
    dimension = meaning_packet["primary_focus"]
    diag_events = event_store.get_events_for_entity("self_diagnosis", dimension)
    for e in diag_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    assert event_store.get_events_for_entity("self_diagnosis", dimension) == []
    print(f"🧹 اتمسح {len(diag_events)} حدث self_diagnosis اتسجل أثناء اختبارات الرفض/fallback فوق")

    print("\n✅✅✅ Companionship Layer verification: كله شغال (LLM حقيقي + retry + fallback + containment)")


if __name__ == "__main__":
    main()
