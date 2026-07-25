# -*- coding: utf-8 -*-
"""
Tests First -- Claim Validator (Architecture v2). اتكتبت قبل أي سطر في
services/claim_validator.py.

الـ Claim Validator بيفحص *template* Companionship (قبل الـ render، مش
بعده -- بعد الـ render فيه أرقام حقيقية شرعية من الـ slots، فحص وقتها
مش هيميّز بين رقم حقيقي ورقم مخترع). الفحص:
  1. صفر رقم خام برّه أي slot (حتمي 100%).
  2. صفر كلمة تقريب/تردد لاصقة بـ slot (heuristic -- موثّق كده صراحة).
  3. صفر نمط نفي/مقارنة حر برّه الـ slots (heuristic -- موثّق كده صراحة).
  4. كل الـ slots المستخدمة لازم تكون فعليًا موجودة في الـ Meaning Packet
     (بيتفحص عبر محاولة render فعلية -- استخدام مباشر لـ renderer.py).

ملحوظة نطاق (موثّقة صراحة، مش مخفية): فحص التقريب دلوقتي عام على كل
الـ slots، مش per-field certainty -- لأن كل الحقائق الحالية exact أصلًا
(مفيش fact حقيقي certainty=approximate لحد دلوقتي). لو ظهر واحد، الفحص
هيحتاج يتخصص وقتها.

مفيش LLM هنا خالص -- Unit Tests بحتة.
"""


def run_test(name, fn):
    try:
        fn()
        print(f"✅ {name}")
        return True
    except AssertionError as e:
        print(f"❌ {name}: {e}")
        return False
    except Exception as e:
        print(f"❌ {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    from services import claim_validator as cv

    results = []

    meaning_packet = {
        "referenced_facts": {"unresolved_conflict.count": 3},
        "fired_inferences": [{"rule_id": "unresolved_conflict_high", "text": "الوضع محتاج مراجعة عاجلة"}],
    }

    # ============================================================
    # 1. قالب سليم -- لازم يعدي وير رندر صح
    # ============================================================
    def test_valid_template_passes():
        result = cv.validate_companionship_output(
            "يا بحورة، لقيت {unresolved_conflict.count} حالات تعارض، و{inference:unresolved_conflict_high}.",
            meaning_packet,
        )
        assert result["valid"] is True, f"errors: {result['errors']}"
        assert result["rendered_text"] == "يا بحورة، لقيت 3 حالات تعارض، والوضع محتاج مراجعة عاجلة."
        assert result["errors"] == []
    results.append(run_test("قالب سليم (slots معروفة، صفر رقم خام) -> valid=True + render صحيح", test_valid_template_passes))

    def test_plain_text_no_slots_valid():
        result = cv.validate_companionship_output("مفيش أي حاجة جديدة النهاردة.", meaning_packet)
        assert result["valid"] is True
        assert result["rendered_text"] == "مفيش أي حاجة جديدة النهاردة."
    results.append(run_test("نص عادي من غير slots ولا أرقام -> valid=True", test_plain_text_no_slots_valid))

    # ============================================================
    # 2. رقم خام برّه أي slot -- حتمي
    # ============================================================
    def test_raw_digit_without_slot_rejected():
        result = cv.validate_companionship_output("عندك 5 حالات تعارض.", meaning_packet)
        assert result["valid"] is False
        assert any(e["type"] == "deterministic" and "5" in e["message"] for e in result["errors"]), result["errors"]
    results.append(run_test("رقم خام برّه أي slot (مفيش slot أصلًا) -> رفض حتمي", test_raw_digit_without_slot_rejected))

    def test_raw_digit_alongside_valid_slot_rejected():
        result = cv.validate_companionship_output(
            "عندك {unresolved_conflict.count} أو 4 حالات.", meaning_packet
        )
        assert result["valid"] is False
        assert any(e["type"] == "deterministic" and "4" in e["message"] for e in result["errors"]), result["errors"]
    results.append(run_test("slot صحيح + رقم خام زيادة جنبه ('3 أو 4') -> رفض حتمي بسبب الرقم الزيادة", test_raw_digit_alongside_valid_slot_rejected))

    def test_digit_inside_slot_name_not_flagged():
        # الأرقام جوه اسم الـ slot نفسه (زي field names ملهاش أرقام فعليًا، لكن للتأكد)
        result = cv.validate_companionship_output("العدد: {unresolved_conflict.count}.", meaning_packet)
        assert result["valid"] is True, result["errors"]
    results.append(run_test("مفيش false-positive على أرقام جوه الـ slot نفسه", test_digit_inside_slot_name_not_flagged))

    # ============================================================
    # 3. كلمات تقريب لاصقة بـ slot -- heuristic
    # ============================================================
    def test_approximation_near_slot_flagged():
        result = cv.validate_companionship_output("حوالي {unresolved_conflict.count} حالات.", meaning_packet)
        assert result["valid"] is False
        assert any(e["type"] == "heuristic" and "تقريب" in e["message"] for e in result["errors"]), result["errors"]
    results.append(run_test("كلمة تقريب ('حوالي') لاصقة بـ slot -> رفض heuristic", test_approximation_near_slot_flagged))

    def test_approximation_far_from_slot_not_flagged():
        # "غالبًا" هنا مش قريبة من أي slot ولا بتتكلم عن رقم -- نص عادي
        result = cv.validate_companionship_output("غالبًا هيبقى كويس، بس خد بالك.", meaning_packet)
        assert result["valid"] is True, result["errors"]
    results.append(run_test("كلمة تقريب بعيدة عن أي slot ومالهاش علاقة برقم -> مش بتتفحص", test_approximation_far_from_slot_not_flagged))

    # ============================================================
    # 4. أنماط نفي/مقارنة حرة -- heuristic
    # ============================================================
    def test_free_negation_flagged():
        result = cv.validate_companionship_output("مفيش أي تعارض خالص.", meaning_packet)
        assert result["valid"] is False
        assert any(e["type"] == "heuristic" and "نفي" in e["message"] for e in result["errors"]), result["errors"]
    results.append(run_test("نفي حر ('مفيش') برّه أي slot -> علامة heuristic", test_free_negation_flagged))

    def test_negation_inside_inference_slot_not_flagged():
        # النفي جوه نص استنتاج معتمد (fired_inferences) -- بيتلصق حرفيًا، مش نص حر
        packet_with_negation_inference = {
            "referenced_facts": {},
            "fired_inferences": [{"rule_id": "frequent_corrections_neutral", "text": "معدل التصحيحات مرتفع -- ملاحظة موضوعية مش مؤشر مشكلة"}],
        }
        result = cv.validate_companionship_output("{inference:frequent_corrections_neutral}", packet_with_negation_inference)
        assert result["valid"] is True, result["errors"]
        assert "مش مؤشر مشكلة" in result["rendered_text"]
    results.append(run_test("نفي جوه inference معتمد (مش نص حر من الموديل) -> بيعدي عادي", test_negation_inside_inference_slot_not_flagged))

    # ============================================================
    # 5. Slot غير معروف -- بيتفحص عبر محاولة render فعلية
    # ============================================================
    def test_unknown_slot_rejected():
        result = cv.validate_companionship_output("{pending_obligation_load.count}", meaning_packet)
        assert result["valid"] is False
        assert result["rendered_text"] is None
        assert any(e["type"] == "deterministic" and "slot" in e["message"].lower() for e in result["errors"]), result["errors"]
    results.append(run_test("slot بيشاور لحاجة مش موجودة في الـ Meaning Packet -> رفض حتمي", test_unknown_slot_rejected))

    # ============================================================
    # 6. أخطاء متعددة بتتجمع كلها، مش أول واحد بس
    # ============================================================
    def test_multiple_errors_accumulate():
        result = cv.validate_companionship_output("مفيش حاجة، بس تقريبًا 9 حالات موجودة.", meaning_packet)
        assert result["valid"] is False
        assert len(result["errors"]) >= 2, f"المفروض أكتر من خطأ واحد (رقم خام + نفي)، لقيت: {result['errors']}"
    results.append(run_test("أكتر من مشكلة في نفس النص -> كل الأخطاء بتتجمع مش أول واحد بس", test_multiple_errors_accumulate))

    def test_no_llm_in_claim_validator_source():
        import services.claim_validator as cv_module
        source = open(cv_module.__file__, encoding="utf-8").read()
        forbidden = ["anthropic", "claude_client", "ask_claude", "openai"]
        found = [t for t in forbidden if t in source]
        assert not found, f"لقيت إشارات LLM في claim_validator.py: {found}"
    results.append(run_test("claim_validator.py مفيهوش أي استدعاء LLM", test_no_llm_in_claim_validator_source))

    # ============================================================
    # 7. Containment: مجموعة ادّعاءات فاضية أو مرفوضة -- ممنوع اختراع
    # طمأنة (زي "كله تمام"، "مفيش داعي للقلق") من غير ما تكون مرخّصة فعليًا
    # (Slot أو inference معتمد). طلب صريح من أحمد -- Tests First قبل أي
    # تعديل على claim_validator.py.
    # ============================================================
    empty_packet = {"referenced_facts": {}, "fired_inferences": []}

    def test_empty_claim_set_rejects_reassurance_1():
        result = cv.validate_companionship_output("كله تمام دلوقتي.", empty_packet)
        assert result["valid"] is False
        assert any("ادّعاء" in e["message"] or "طمأنة" in e["message"] for e in result["errors"]), result["errors"]
    results.append(run_test("مجموعة ادّعاءات فاضية + 'كله تمام' حر -> رفض (طمأنة غير مرخّصة)", test_empty_claim_set_rejects_reassurance_1))

    def test_empty_claim_set_rejects_reassurance_2():
        result = cv.validate_companionship_output("مفيش حاجة تقلق عليها خالص.", empty_packet)
        assert result["valid"] is False
    results.append(run_test("مجموعة ادّعاءات فاضية + 'مفيش حاجة تقلق' -> رفض", test_empty_claim_set_rejects_reassurance_2))

    def test_empty_claim_set_rejects_reassurance_3():
        result = cv.validate_companionship_output("مفيش أي مشكلة النهاردة.", empty_packet)
        assert result["valid"] is False
    results.append(run_test("مجموعة ادّعاءات فاضية + 'مفيش أي مشكلة النهاردة' -> رفض", test_empty_claim_set_rejects_reassurance_3))

    def test_status_claim_rejected_even_with_other_facts_present():
        # نفس منطق الطمأنة لازم يتفحص حتى لو فيه حقائق تانية متاحة -- مش بس
        # وقت ما الـpacket فاضية بالكامل. الطمأنة نفسها لسه مش مرخّصة إلا
        # عبر inference معتمد.
        result = cv.validate_companionship_output(
            "عندك {unresolved_conflict.count} تعارضات، بس متقلقش، الوضع مستقر.",
            meaning_packet,
        )
        assert result["valid"] is False
        assert any(e["type"] == "heuristic" for e in result["errors"])
    results.append(run_test("طمأنة حرة جنب Slot صحيح -- لسه ترفض لأنها هي نفسها غير مرخّصة", test_status_claim_rejected_even_with_other_facts_present))

    def test_licensed_reassurance_via_inference_slot_passes():
        # الطمأنة المرخّصة الوحيدة: نص inference معتمد سلفًا، متلصق عبر Slot،
        # مش متأليف حر من الموديل. نفس منطق "النفي جوه inference" الموجود.
        packet_with_all_clear = {
            "referenced_facts": {},
            "fired_inferences": [{"rule_id": "all_clear", "text": "مفيش حاجة تقلق عليها دلوقتي، كل حاجة متابعة"}],
        }
        result = cv.validate_companionship_output("{inference:all_clear}", packet_with_all_clear)
        assert result["valid"] is True, result["errors"]
        assert "مفيش حاجة تقلق" in result["rendered_text"]
    results.append(run_test("طمأنة مرخّصة عبر inference معتمد (مش نص حر) -> بتعدي عادي", test_licensed_reassurance_via_inference_slot_passes))

    def test_pure_conversational_framing_with_empty_claims_still_valid():
        # المحادثة الخالصة (بدون أي ادّعاء وقائعي) تفضل حرة تمامًا حتى مع
        # مجموعة ادّعاءات فاضية -- المبدأ الدستوري: القيد على الادّعاء
        # نفسه، مش على الحوار.
        result = cv.validate_companionship_output("أنا معاك، تحب نتكلم في حاجة تانية؟", empty_packet)
        assert result["valid"] is True, result["errors"]
    results.append(run_test("حوار خالص (مفيش ادّعاء) مع مجموعة ادّعاءات فاضية -> يفضل حر ويعدي", test_pure_conversational_framing_with_empty_claims_still_valid))

    def test_existing_generic_smalltalk_regression_still_valid():
        # Regression: الجملة العادية من test_plain_text_no_slots_valid (بُعد
        # عام مش موضوع طمأنة عن الحالة المتابَعة) لازم تفضل valid زي ما
        # كانت -- إضافة قواعد الطمأنة الجديدة مينفعش تكسر السلوك القديم.
        result = cv.validate_companionship_output("مفيش أي حاجة جديدة النهاردة.", meaning_packet)
        assert result["valid"] is True, result["errors"]
    results.append(run_test("Regression: كلام عادي غير متعلق بموضوع الطمأنة لسه valid", test_existing_generic_smalltalk_regression_still_valid))

    # ============================================================
    # 8. Regression حقيقي -- تشغيلة تكامل فعلية (test_pipeline_integration.py)
    # طلعت النص ده بالحرف من LLM حقيقي، وكان لازم يترفض ومفيش رفض حصل: تناقض
    # وقائعي ("محلولة") مع حقيقة مرخّصة (unresolved_conflict لسه غير محلول)،
    # من غير رقم خام، slot غير معروف، تقريب، أو نمط طمأنة من القائمة القديمة.
    # طلب صريح من أحمد -- الفرق عن بند 7: ده تناقض مباشر مع حقيقة موثّقة،
    # مش مجرد طمأنة عامة غير مرخّصة.
    # ============================================================
    conflict_packet = {
        "referenced_facts": {"unresolved_conflict.count": 1},
        "fired_inferences": [{"rule_id": "unresolved_conflict_elevated", "text": "محتاج مراجعتك"}],
    }

    def test_regression_real_output_resolved_contradiction_rejected():
        # النص الحقيقي بالحرف من test_pipeline_integration.py (بعد استبدال
        # الرقم الخام بـSlot -- الموديل الحقيقي كان بيستخدم Slot فعلي هنا،
        # المشكلة مش في الرقم، في كلمة "محلولة" الحرة).
        result = cv.validate_companionship_output(
            "عندك {unresolved_conflict.count} خلافات لسه متفتحة ومحلولة، وده مش قليل يعني.",
            conflict_packet,
        )
        assert result["valid"] is False, "المفروض يترفض -- 'محلولة' بتتناقض مع unresolved_conflict.count=1 الموثّق"
    results.append(run_test(
        "Regression حقيقي: 'محلولة' حرة بتتناقض مع تعارض غير محلول موثّق -> رفض",
        test_regression_real_output_resolved_contradiction_rejected,
    ))

    def test_regression_real_output_synonym_contradiction_rejected():
        # نفس الفئة، مرادف مختلف -- تشغيلة تكامل تانية (بعد إصلاح "محلولة")
        # طلّعت نفس التناقض بكلمة مختلفة من LLM حقيقي: "معلقة ومحسومة".
        # اتحفظ بالحرف زي ما طلب أحمد -- إثبات إن القائمة محتاجة تتوسّع
        # للمرادفات القريبة، مش بس الكلمة الأولى اللي ظهرت.
        result = cv.validate_companionship_output(
            "في بالي إن عندك {unresolved_conflict.count} من الخلافات لسه معلقة ومحسومة.",
            conflict_packet,
        )
        assert result["valid"] is False, "المفروض يترفض -- 'محسومة' مرادف لـ'محلولة'، نفس التناقض"
    results.append(run_test(
        "Regression حقيقي #2: 'محسومة' (مرادف) بتتناقض مع تعارض غير محلول موثّق -> رفض",
        test_regression_real_output_synonym_contradiction_rejected,
    ))

    def test_resolution_word_without_active_count_not_flagged():
        # لو مفيش count فعلي موثّق للبُعد ده أصلًا (مثلًا level=none، مفيش
        # مفتاح count في referenced_facts) -- مفيش حقيقة تتناقض معاها، فمفيش
        # داعي نرفض كلمة "اتحل" لو جت في سياق تاني تمامًا (مش عن البُعد ده).
        result = cv.validate_companionship_output("خلصت شغلي بدري النهاردة.", empty_packet)
        assert result["valid"] is True, result["errors"]
    results.append(run_test("كلمة 'خلص' في سياق عادي (مفيش count موثّق يتناقض معاه) -> يعدي", test_resolution_word_without_active_count_not_flagged))

    # ============================================================
    print(f"\n{sum(results)}/{len(results)} اختبار عدّى")
    if all(results):
        print("✅✅✅ كل الاختبارات عدّت")
    else:
        print("❌ فيه اختبارات فشلت")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
