# -*- coding: utf-8 -*-
"""
تحقق فعلي من Verified Expression Layer (Stage 6/7) ضد Firestore الحقيقي:
- الضمان الرسمي التلاتة: Information Containment (تلميح غير مباشر عبر بنية
  الكود)، Verbatim Match Validator، Evidence Trace.
- Active Expression (backend بحت، صفر LLM).
- Passive Expression عبر request_verified_expression + verify_and_finalize.
- دمج مع claude_service._execute_tool (الأداة الفعلية اللي الموديل هيستخدمها).

بيستخدم القسط الآمن (Credit Agricole 2032) لتوليد بيانات حقيقية، وبينضف
كل حاجة في الآخر.
"""

from fake_firestore import install_fake_firestore
from services import (
    loan_service, loan_commands, event_store,
    self_state_engine, decision_engine, verified_expression, expression_vocabulary,
)
from config import SELF_STATE_COLLECTION, STATE_SNAPSHOTS_COLLECTION, EXPRESSIONS_COLLECTION

PROGRAM = "Credit Agricole"
MONTH_KEY = "01/06/2032"
TEST_CHAT_ID = 999999


def main():
    install_fake_firestore()
    from services.firebase_service import firestore_db

    program = loan_service._find_program(PROGRAM)
    idx = len(program["installments"]) - 1
    identity_key = f"{program['id']}_{idx}"
    original_paid = loan_service.is_paid(program["id"], idx)
    assert original_paid is False

    existing = event_store.get_events_for_entity("loan_installment", identity_key)
    assert existing == [], f"توقف احترازيًا -- لقيت {len(existing)} حدث سابق"

    pre_existing_diag_conflict = event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict")
    assert pre_existing_diag_conflict == [], f"توقف احترازيًا -- لقيت {len(pre_existing_diag_conflict)} حدث self_diagnosis سابق على unresolved_conflict"
    pre_existing_diag_tracking = event_store.get_events_for_entity("self_diagnosis", "tracking_stability")
    assert pre_existing_diag_tracking == [], f"توقف احترازيًا -- لقيت {len(pre_existing_diag_tracking)} حدث self_diagnosis سابق على tracking_stability"

    created_snapshots, created_expressions, created_loan_events = [], [], []

    # ============================================================
    # Part A: الأداة مسجّلة صح في claude_service، ومفيش "mode" مكشوف للموديل
    # ============================================================
    from services.claude_service import TOOLS
    tool_def = next((t for t in TOOLS if t["name"] == "request_verified_expression"), None)
    assert tool_def is not None, "الأداة مش مسجّلة في TOOLS"
    assert "mode" not in tool_def["input_schema"]["properties"], "❌ mode مكشوفة للموديل -- ده يكسر Information Containment"
    assert set(tool_def["input_schema"]["properties"]["dimension"]["enum"]) == {
        "unresolved_conflict", "pending_obligation_load", "tracking_stability"
    }
    print("✅ الأداة مسجّلة صح، ومفيش 'mode' مكشوفة للموديل (Information Containment)")

    # ============================================================
    # Part B: Passive expression -- حالة "none" (مفيش دليل مطلوب، لازم verified=true)
    # ============================================================
    result_none = verified_expression.request_verified_expression("tracking_stability", chat_id=TEST_CHAT_ID)
    assert result_none["verified"] is True
    assert result_none["text"] == expression_vocabulary.CLOSED_VOCABULARY[("tracking_stability", "none", "passive")]
    assert result_none["expression_id"] is not None
    created_expressions.append(result_none["expression_id"])
    print(f"✅ Passive 'none' -> verified=true, نص من القاموس بالحرف: {result_none['text']}")

    # تأكيد الـ Evidence Trace: expression -> state -> (evidence فاضية هنا لأن level=none)
    expr_doc = firestore_db.collection(EXPRESSIONS_COLLECTION).document(result_none["expression_id"]).get()
    assert expr_doc.exists
    expr_data = expr_doc.to_dict()
    state_doc = firestore_db.collection(STATE_SNAPSHOTS_COLLECTION).document(expr_data["state_id"]).get()
    assert state_doc.exists
    created_snapshots.append(expr_data["state_id"])
    print(f"✅ Evidence Trace: expression_id={result_none['expression_id']} -> state_id={expr_data['state_id']} -- الاتنين موجودين فعليًا في Firestore")

    # نقفل الدورة دي (زي ما بيحصل فعليًا آخر كل رد) قبل ما نبدأ دورة تانية
    verified_expression.verify_and_finalize(TEST_CHAT_ID, result_none["text"])

    # ============================================================
    # Part C: نولّد تعارض حقيقي، ونتأكد إن Passive لـ unresolved_conflict بيرجع evidence حقيقية
    # ============================================================
    ok1, _, e1 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, True, chat_id=TEST_CHAT_ID)
    assert ok1
    created_loan_events.append(e1)
    ok2, _, e2 = loan_commands.loan_record_installment(PROGRAM, MONTH_KEY, False, chat_id=TEST_CHAT_ID)
    assert ok2 is False  # اترفضت (Stage 4) -- سجّلت conflict_status=pending event

    result_conflict = verified_expression.request_verified_expression("unresolved_conflict", chat_id=TEST_CHAT_ID)
    assert result_conflict["verified"] is True
    assert result_conflict["text"] == "عندي 1 تعارض غير محلول محتاج مراجعتك."
    created_expressions.append(result_conflict["expression_id"])
    print(f"✅ Passive 'elevated' مع تعارض حقيقي: {result_conflict['text']}")

    expr_doc2 = firestore_db.collection(EXPRESSIONS_COLLECTION).document(result_conflict["expression_id"]).get().to_dict()
    state_doc2 = firestore_db.collection(STATE_SNAPSHOTS_COLLECTION).document(expr_doc2["state_id"]).get().to_dict()
    created_snapshots.append(expr_doc2["state_id"])
    evidence_ids = state_doc2["dimensions"]["unresolved_conflict"]["evidence_event_ids"]
    assert len(evidence_ids) == 1
    real_event = event_store.get_event(evidence_ids[0])
    assert real_event is not None and real_event["attribute"] == "conflict_status"
    print(f"✅ الـ evidence_event_ids في الـ StateSnapshot بترجع لحدث حقيقي فعلاً: {evidence_ids[0]}")

    # ============================================================
    # Part D: Verbatim Match Validator -- تطابق صح يعدي زي ما هو
    # ============================================================
    fake_llm_reply_correct = "تمام يا بحورة، بالنسبة للأقساط: " + result_conflict["text"]
    finalized = verified_expression.verify_and_finalize(TEST_CHAT_ID, fake_llm_reply_correct)
    assert finalized == fake_llm_reply_correct, "❌ رد مطابق اتغيّر وهو مفروض يعدي زي ما هو"
    print("✅ Verbatim Match Validator: رد مطابق بالحرف عدّى من غير أي تعديل")

    mismatches_after_d = [
        e for e in event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict")
        if e["attribute"] == "verbatim_mismatch"
    ]
    assert len(mismatches_after_d) == 0, "المفروض صفر verbatim_mismatch بعد Part D (تطابق صح)"
    print("✅ H2: تطابق صح (Part D) -> صفر حدث verbatim_mismatch")

    # ============================================================
    # Part E: Verbatim Match Validator -- محاولة "تحسين صياغة" لازم تترفض وتتصحح
    # ============================================================
    result_conflict2 = verified_expression.request_verified_expression("unresolved_conflict", chat_id=TEST_CHAT_ID)
    created_expressions.append(result_conflict2["expression_id"])
    expr_doc3 = firestore_db.collection(EXPRESSIONS_COLLECTION).document(result_conflict2["expression_id"]).get().to_dict()
    created_snapshots.append(expr_doc3["state_id"])
    fake_llm_reply_paraphrased = "معلش يا بحورة، لسه في تعارض واحد مش محلول محتاج نظرة منك"  # نفس المعنى، مش نفس النص بالحرف
    finalized2 = verified_expression.verify_and_finalize(TEST_CHAT_ID, fake_llm_reply_paraphrased)
    assert result_conflict2["text"] in finalized2, "❌ النص الأصلي المفروض يترجع لو الموديل غيّر الصياغة"
    assert finalized2 != fake_llm_reply_paraphrased
    print(f"✅ Verbatim Match Validator: إعادة صياغة اترفضت، النص الأصلي اترجع: {finalized2}")

    # ============================================================
    # Part F: verified=false لبُعد مش معروف -- مفيش تخمين
    # ============================================================
    result_unknown = verified_expression.request_verified_expression("some_future_dimension", chat_id=TEST_CHAT_ID)
    assert result_unknown["verified"] is False
    assert "ناقصة" in result_unknown["text"]
    print(f"✅ بُعد مش معروف -> verified=false: {result_unknown['text']}")

    # ============================================================
    # Part G: Active Expression -- backend بحت، صفر LLM
    # (بنستخدم send_active_expression مباشرة بمستوى محدد -- من غير ما ننادي
    # decision_engine.decide_expression هنا، عشان منسيبش أثر في الحالة
    # المخزّنة الحقيقية بتاعته من بيانات اختبار)
    # ============================================================
    # مش هيبقى active فعليًا (مستوى elevated مش high) -- نتأكد إن send_active_expression بترفض صح
    active_attempt_wrong_level = verified_expression.send_active_expression("unresolved_conflict", "high", TEST_CHAT_ID)
    assert active_attempt_wrong_level is None, "❌ المفروض ترفض لإن المستوى الفعلي elevated مش high"
    print("✅ Active اترفضت صح -- المستوى الفعلي (elevated) مش المستوى المطلوب (high)")

    # نولّد تعارضين إضافيين (تلاتة إجمالي) عشان نوصل لـ high فعليًا -- على أقساط بعيدة تانية آمنة
    safe_targets = []
    for offset in range(2, 4):  # آخر قسطين قبل الأخير في نفس البرنامج -- برضه بعيدين جدًا (2032)
        idx2 = len(program["installments"]) - offset
        inst2 = program["installments"][idx2]
        key2 = f"{program['id']}_{idx2}"
        assert loan_service.is_paid(program["id"], idx2) is False, f"توقف احترازيًا -- {key2} مش False"
        pre_events = event_store.get_events_for_entity("loan_installment", key2)
        assert pre_events == [], f"توقف احترازيًا -- {key2} عليه أحداث سابقة"
        safe_targets.append((inst2["date"], key2, idx2))

    for date_key, key2, idx2 in safe_targets:
        okx, _, ex = loan_commands.loan_record_installment(PROGRAM, date_key, True, chat_id=TEST_CHAT_ID)
        assert okx
        created_loan_events.append(ex)
        okx2, _, _ = loan_commands.loan_record_installment(PROGRAM, date_key, False, chat_id=TEST_CHAT_ID)
        assert okx2 is False  # رفض + conflict_status=pending event

    conflict_now = self_state_engine.compute_unresolved_conflict()
    assert conflict_now["count"] == 3 and conflict_now["level"] == "high", conflict_now
    print(f"✅ 3 تعارضات حقيقية -> level='high': {conflict_now}")

    # نعمل mock لـ bot.send_message عشان منبعتش رسالة حقيقية لأي حد (TEST_CHAT_ID
    # مش شات حقيقي على أي حال) -- بنتحقق إن الدالة وصلت فعليًا لنقطة الإرسال
    # بالنص والـ chat_id الصح، من غير ما نضرب Telegram API الحقيقي.
    import bot as bot_module
    sent_calls = []
    original_send_message = bot_module.bot.send_message
    bot_module.bot.send_message = lambda chat_id, text, **kw: sent_calls.append((chat_id, text))
    try:
        active_expression_id = verified_expression.send_active_expression("unresolved_conflict", "high", TEST_CHAT_ID)
    finally:
        bot_module.bot.send_message = original_send_message

    assert active_expression_id is not None, "❌ المفروض تبعت فعليًا -- الشروط كلها متحققة"
    assert len(sent_calls) == 1
    assert sent_calls[0] == (TEST_CHAT_ID, "تنبيه: ظهر تعارض غير محلول يحتاج مراجعتك.")
    print(f"✅ bot.send_message اتنادت فعليًا بالنص والـ chat_id الصح (mocked عشان منبعتش رسالة حقيقية): {sent_calls[0]}")
    created_expressions.append(active_expression_id)
    active_doc = firestore_db.collection(EXPRESSIONS_COLLECTION).document(active_expression_id).get().to_dict()
    assert active_doc["mode"] == "active"
    assert active_doc["rendered_text"] == "تنبيه: ظهر تعارض غير محلول يحتاج مراجعتك."
    created_snapshots.append(active_doc["state_id"])
    print(f"✅ Active اتبعتت فعليًا (صفر LLM): {active_doc['rendered_text']} | expression_id={active_expression_id}")

    # ============================================================
    # Part H: Self-Diagnosis -- verbatim_mismatch (Tests First، نطاق ضيق:
    # تسجيل الحدث الخام بس، بدون استنتاج تشخيصي -- طلب أحمد صراحة 2026-07-24)
    # ============================================================

    # H1: مفيش pending verification أصلاً -- صفر حدث، والنص يرجع زي ما هو
    fresh_chat_id = TEST_CHAT_ID + 12345
    baseline_conflict_diag = len(event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict"))
    untouched_text = "رد عادي مفيهوش أي تعبير معتمد قيد الانتظار."
    finalized_no_pending = verified_expression.verify_and_finalize(fresh_chat_id, untouched_text)
    assert finalized_no_pending == untouched_text, "❌ المفروض النص يرجع زي ما هو -- مفيش pending أصلاً"
    after_no_pending = len(event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict"))
    assert after_no_pending == baseline_conflict_diag, "المفروض صفر حدث self_diagnosis لما مفيش pending verification"
    print("✅ H1: مفيش pending verification -> صفر حدث self_diagnosis، والنص رجع زي ما هو")

    # H3: رفض/تصحيح في Part E فوق -- حدث واحد بالظبط، مربوط بالـ expression_id الصح
    diag_after_mismatch = event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict")
    mismatches_after_e = [e for e in diag_after_mismatch if e["attribute"] == "verbatim_mismatch"]
    assert len(mismatches_after_e) == 1, f"المفروض حدث verbatim_mismatch واحد بالظبط بعد Part E، لقيت {len(mismatches_after_e)}"
    assert mismatches_after_e[0]["raw_context"]["expression_id"] == result_conflict2["expression_id"], \
        "المفروض expression_id المسجّل يطابق التعبير اللي سبب الرفض بالظبط"
    real_evt = event_store.get_event(mismatches_after_e[0]["event_id"])
    assert real_evt is not None, "evidence event مش بيرجع لحدث حقيقي"
    print(f"✅ H3: حدث verbatim_mismatch واحد اتسجل صح من Part E، مربوط بـ expression_id={result_conflict2['expression_id']}")

    # H4: كذا تعبير pending في نفس الدورة -- حدث واحد بس للي فعلاً اترفض، مش حدث لكل pending
    multi_chat_id = TEST_CHAT_ID + 54321
    result_multi_ok = verified_expression.request_verified_expression("tracking_stability", chat_id=multi_chat_id)
    created_expressions.append(result_multi_ok["expression_id"])
    expr_doc_multi_ok = firestore_db.collection(EXPRESSIONS_COLLECTION).document(result_multi_ok["expression_id"]).get().to_dict()
    created_snapshots.append(expr_doc_multi_ok["state_id"])

    result_multi_bad = verified_expression.request_verified_expression("unresolved_conflict", chat_id=multi_chat_id)
    created_expressions.append(result_multi_bad["expression_id"])
    expr_doc_multi_bad = firestore_db.collection(EXPRESSIONS_COLLECTION).document(result_multi_bad["expression_id"]).get().to_dict()
    created_snapshots.append(expr_doc_multi_bad["state_id"])

    baseline_tracking_mismatches = len([
        e for e in event_store.get_events_for_entity("self_diagnosis", "tracking_stability")
        if e["attribute"] == "verbatim_mismatch"
    ])

    fake_multi_reply = result_multi_ok["text"] + " -- بس بالنسبة للتعارضات، الوضع فيه مراجعة مطلوبة قريبًا"  # T1 بالحرف، T2 معاد صياغته
    finalized_multi = verified_expression.verify_and_finalize(multi_chat_id, fake_multi_reply)

    assert result_multi_ok["text"] in finalized_multi, "❌ التعبير المطابق (tracking_stability) المفروض يفضل زي ما هو"
    assert result_multi_bad["text"] in finalized_multi, "❌ التعبير المرفوض (unresolved_conflict) المفروض يترجع بالحرف"

    tracking_mismatches_after = [
        e for e in event_store.get_events_for_entity("self_diagnosis", "tracking_stability")
        if e["attribute"] == "verbatim_mismatch"
    ]
    assert len(tracking_mismatches_after) == baseline_tracking_mismatches, \
        "المفروض صفر حدث جديد لـ tracking_stability -- كان تطابق صح، مش رفض"

    conflict_mismatches_after_h4 = [
        e for e in event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict")
        if e["attribute"] == "verbatim_mismatch"
    ]
    new_events_h4 = [e for e in conflict_mismatches_after_h4 if e["event_id"] != mismatches_after_e[0]["event_id"]]
    assert len(new_events_h4) == 1, (
        f"المفروض حدث verbatim_mismatch واحد جديد بس (2 pending، واحد بس اترفض)، لقيت {len(new_events_h4)}"
    )
    assert new_events_h4[0]["raw_context"]["expression_id"] == result_multi_bad["expression_id"], \
        "المفروض expression_id الحدث الجديد يطابق التعبير اللي فعليًا اترفض في الدورة دي"
    print(f"✅ H4: 2 pending في نفس الدورة، واحد بس اترفض -> حدث verbatim_mismatch واحد بالظبط (مش 2)، مربوط بـ expression_id={result_multi_bad['expression_id']}")

    # ============================================================
    # Part I: سياسة فشل event_store.record_event عند verify_and_finalize --
    # best-effort، مينفعش يمنع وصول التصحيح الفعلي (قرار أحمد 2026-07-24).
    # الضمانة الرسمية هي الـVerbatim Match Validator نفسه (النص المصحَّح
    # لازم يوصل)، مش تسجيل self_diagnosis -- ده رصد ثانوي بحت.
    # ============================================================
    failure_chat_id = TEST_CHAT_ID + 99999
    result_failure = verified_expression.request_verified_expression("tracking_stability", chat_id=failure_chat_id)
    created_expressions.append(result_failure["expression_id"])
    expr_doc_failure = firestore_db.collection(EXPRESSIONS_COLLECTION).document(result_failure["expression_id"]).get().to_dict()
    created_snapshots.append(expr_doc_failure["state_id"])

    baseline_tracking_before_failure = len(event_store.get_events_for_entity("self_diagnosis", "tracking_stability"))

    def _raising_record_event(*args, **kwargs):
        raise RuntimeError("محاكاة فشل كتابة حقيقي في Event Store")

    original_record_event = event_store.record_event
    event_store.record_event = _raising_record_event
    try:
        fake_reply_forces_mismatch = "رد بصياغة تانية خالص مش مطابقة للنص المعتمد"
        finalized_failure = verified_expression.verify_and_finalize(failure_chat_id, fake_reply_forces_mismatch)
    finally:
        event_store.record_event = original_record_event

    assert result_failure["text"] in finalized_failure, (
        "❌ فشل تسجيل self_diagnosis المفروض ميمنعش التصحيح الفعلي من الوصول -- "
        "الـVerbatim Match Validator هو الضمانة الرسمية، مش تسجيل التشخيص"
    )
    after_failure = len(event_store.get_events_for_entity("self_diagnosis", "tracking_stability"))
    assert after_failure == baseline_tracking_before_failure, "المفروض صفر حدث اتسجل فعليًا (الكتابة فشلت عمدًا ومتلقّطة)"
    print("✅ Part I: فشل event_store.record_event اتلقّط (best-effort) -- التصحيح الفعلي وصل زي ما المفروض برضه")

    # ============================================================
    # تنظيف كامل
    # ============================================================
    print("\n🧹 بدء التنظيف...")

    for eid in set(created_expressions):
        firestore_db.collection(EXPRESSIONS_COLLECTION).document(eid).delete()
    for sid in set(created_snapshots):
        firestore_db.collection(STATE_SNAPSHOTS_COLLECTION).document(sid).delete()

    # رجّع كل الأقساط لأصلها ومسح كل أحداثها
    all_targets = [(MONTH_KEY, identity_key, idx)] + safe_targets
    for date_key, key2, idx2 in all_targets:
        okc, _, _ = loan_commands.loan_update_installment(
            PROGRAM, date_key, paid=False, reason="استرجاع الحالة الأصلية بعد تحقق Stage 6/7"
        )
        assert okc
        evs = event_store.get_events_for_entity("loan_installment", key2)
        for e in evs:
            firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
        assert event_store.get_events_for_entity("loan_installment", key2) == []
        assert loan_service.is_paid(program["id"], idx2) is False

    final_state = self_state_engine.compute_unresolved_conflict()
    assert final_state["count"] == 0, final_state
    print(f"✅ كل الأقساط رجعت لأصلها، unresolved_conflict رجع لـ 0: {final_state}")

    diag_conflict_events = event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict")
    for e in diag_conflict_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    assert event_store.get_events_for_entity("self_diagnosis", "unresolved_conflict") == []

    diag_tracking_events = event_store.get_events_for_entity("self_diagnosis", "tracking_stability")
    for e in diag_tracking_events:
        firestore_db.collection(event_store.EVENTS_COLLECTION).document(e["event_id"]).delete()
    assert event_store.get_events_for_entity("self_diagnosis", "tracking_stability") == []

    print(f"🧹 اتمسح {len(diag_conflict_events)} حدث self_diagnosis (unresolved_conflict) و{len(diag_tracking_events)} (tracking_stability)")

    print("\n✅✅✅ Stage 6/7 verification: القاموس المقفول + Evidence Trace + Verbatim Validator + Active backend-only كلهم شغالين صح")


if __name__ == "__main__":
    main()
