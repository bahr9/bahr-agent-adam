# -*- coding: utf-8 -*-
"""
Tests First -- Self State Core (Milestone: Health Status, Internal Warnings,
Confidence, Current Mode, Diagnosis Summary).

نفس منهجية باقي اختبارات المشروع: تشغيل فعلي (مش نظري)، بعضها وحدات نقية
(بدون Firestore، صفر تكلفة)، وبعضها تكامل حقيقي ضد Firestore الحي (بيانات
اختبار محقونة مباشرة عبر event_store.record_event، وبتتمسح بعد التأكيد --
نفس أسلوب test_self_diagnosis.py بالحرف).

صفر استدعاء LLM في الملف ده كله -- self_state_core.py وself_diagnosis.py
مايلمسوش companionship_layer أصلًا، فمفيش تكلفة Anthropic هنا خالص.
"""

import pytest

from fake_firestore import install_fake_firestore, use_fake_firestore
from services import event_store, self_diagnosis, self_state_core, self_state_engine, verified_expression


@pytest.fixture(autouse=True)
def _isolated_store():
    """شوف الشرح في test_tool_lifecycle_diagnostics.py -- نفس الوصلة
    المقطوعة: العزل جوه `main()` وpytest مبينديهاش. الملف ده كان بيعدّي
    بالصدفة، بس كان بيعتمد على fake مسرّب من ملف تاني زي أخوه."""
    with use_fake_firestore():
        yield


TEST_ENTITY_ID = "test_self_state_core"
TEST_CHAT_ID = 999001


def test_render_report_no_duplicate_lines():
    """
    (حادثة 2026-07-27، بند F) render_report كان بيكرر تفسير fallback/
    rejection/mismatch مرتين حرفيًا -- مرة كـ internal_warnings bullet
    (لما count > 0)، ومرة تانية جوه diagnosis_summary (اللي أصلًا بيغطّي
    الثلاثة دول دايمًا). اتأكد بإعادة إنتاج حقيقية على بيانات حية، واتصلح.
    """
    core = {
        "health_status": "DEGRADED",
        "health_status_explanation": "-",
        "internal_warnings": [
            {"source": "pending_obligation_load", "category": "domain", "level": "concern", "count": 7,
             "evidence_event_ids": [], "explanation": "UNIQUE_DOMAIN_TEXT_ABC"},
            {"source": "verbatim_mismatch", "category": "runtime", "count": 3,
             "evidence_event_ids": ["e1", "e2", "e3"], "explanation": "UNIQUE_MISMATCH_TEXT_XYZ"},
        ],
        "confidence": "full",
        "confidence_evidence_event_ids": [],
        "current_mode": "degraded",
        "current_mode_evidence_event_ids": [],
        "diagnosis_summary": "مفيش أي تفعيل fallback في آخر 30 يوم مفيش أي رفض من claim_validator في آخر 30 يوم UNIQUE_MISMATCH_TEXT_XYZ",
        "diagnosis_summary_evidence_event_ids": ["e1", "e2", "e3"],
        "computed_at": "irrelevant",
        "computation_errors": [],
    }

    report = self_state_core.render_report(core)
    assert report.count("UNIQUE_MISMATCH_TEXT_XYZ") == 1, f"نص التشخيص المتكرر لسه بيتكرر مرتين: {report}"
    assert report.count("UNIQUE_DOMAIN_TEXT_ABC") == 1, "تحذير الـdomain (مش مغطى في diagnosis_summary) لازم يظهر مرة واحدة"
    print("✅ render_report: صفر تكرار -- تفسير fallback/rejection/mismatch بيظهر مرة واحدة بس (جوه diagnosis_summary)")


def test_pure_functions():
    """
    Part A -- الدوال النقية (compute_health_status/compute_confidence/
    compute_current_mode): صفر I/O، مدخلات صناعية، تغطية كاملة للحالات
    الأربعة + انتشار unknown/degraded.
    """
    healthy = {"count": 0, "evidence_event_ids": [], "explanation": "-"}
    one_fallback = {"count": 1, "evidence_event_ids": ["e1"], "explanation": "-"}
    three_rejections = {"count": 3, "evidence_event_ids": ["e1", "e2", "e3"], "explanation": "-"}
    one_mismatch = {"count": 1, "evidence_event_ids": ["e1"], "explanation": "-"}

    # HEALTHY: الثلاثة صفر، الدليل اتقرا صح
    h = self_state_core.compute_health_status(healthy, healthy, healthy, True)
    assert h["status"] == "HEALTHY", h

    # WATCH: fallback >= 1، مفيش شرط DEGRADED
    h = self_state_core.compute_health_status(one_fallback, healthy, healthy, True)
    assert h["status"] == "WATCH", h

    # DEGRADED via rejection >= 3 (حتى لو fallback=0)
    h = self_state_core.compute_health_status(healthy, three_rejections, healthy, True)
    assert h["status"] == "DEGRADED", h

    # DEGRADED via mismatch >= 1 (حتى لو fallback=0 و rejection=0)
    h = self_state_core.compute_health_status(healthy, healthy, one_mismatch, True)
    assert h["status"] == "DEGRADED", h

    # UNKNOWN: الدليل ماقدرش يتقرا -- بيتجاهل أي قيم تانية
    h = self_state_core.compute_health_status(None, None, None, False)
    assert h["status"] == "UNKNOWN", h
    print("✅ compute_health_status: الحالات الأربعة (HEALTHY/WATCH/DEGRADED×2/UNKNOWN) صح")

    # Confidence
    assert self_state_core.compute_confidence([]) == "full"
    assert self_state_core.compute_confidence(["err1"]) == "degraded"
    assert self_state_core.compute_confidence(["err1", "err2", "err3", "err4"]) == "unknown"
    print("✅ compute_confidence: full/degraded/unknown صح")

    # Current Mode -- اشتقاق بحت، انتشار unknown/degraded له الأولوية
    assert self_state_core.compute_current_mode("HEALTHY", [], "full") == "normal"
    assert self_state_core.compute_current_mode("WATCH", [{"x": 1}], "full") == "attention_needed"
    assert self_state_core.compute_current_mode("HEALTHY", [], "unknown") == "unknown", "لازم unknown ينتشر حتى لو health_status هادئ"
    assert self_state_core.compute_current_mode("HEALTHY", [], "degraded") == "degraded", "لازم degraded confidence ينتشر"
    assert self_state_core.compute_current_mode("DEGRADED", [], "full") == "degraded"
    print("✅ compute_current_mode: كل التركيبات (بما فيها انتشار unknown/degraded) صح")


def test_warning_categories():
    """
    Part A.1 -- تصحيح دلالي 2026-07-27: كل عنصر في internal_warnings لازم
    "category" صريحة ("domain" للأبعاد الأقساط، "runtime" للعدادات التشخيصية)،
    بدون أي تغيير في explanation أو أي حقل تاني. صفر Firestore.
    """
    self_state = {
        "unresolved_conflict": {"level": "high", "count": 3, "evidence_event_ids": ["e1"], "explanation": "-"},
        "pending_obligation_load": {"level": "none", "count": 0, "evidence_event_ids": [], "explanation": "-"},
        "tracking_stability": {"level": "none", "count": 0, "evidence_event_ids": [], "explanation": "-"},
        "computed_at": "irrelevant",
    }
    zero = {"count": 0, "evidence_event_ids": [], "explanation": "-"}
    one = {"count": 1, "evidence_event_ids": ["e2"], "explanation": "-"}

    warnings = self_state_core.compute_internal_warnings(self_state, None, one, zero, zero, True)
    by_source = {w["source"]: w for w in warnings}

    assert by_source["unresolved_conflict"]["category"] == "domain", by_source
    assert by_source["fallback_activation"]["category"] == "runtime", by_source
    print("✅ compute_internal_warnings: category صح (domain للأبعاد، runtime للتشخيص)، صفر تغيير في explanation")

    # حالة الفشل (unavailable) -- self_state_err وdiagnosis_ok=False سوا هنا،
    # فبتظهر تحذيرين "unavailable"؛ بنلاقيهم بالـsource مش بالـindex
    warnings_fail = self_state_core.compute_internal_warnings(None, "read failed", zero, zero, zero, False)
    fail_by_source = {w["source"]: w for w in warnings_fail}
    assert fail_by_source["loans_self_state"]["category"] == "domain", fail_by_source
    assert fail_by_source["self_diagnosis"]["category"] == "runtime", fail_by_source
    print("✅ حالات 'unavailable' (فشل قراءة self_state/self_diagnosis) معاهم category صح لكل واحدة")

    # إثبات بنيوي (مش بس ملاحظة): evidence بُعد unresolved_conflict ("e1")
    # مش موجودة أصلًا في مدخلات compute_health_status -- الدالة مالهاش وصول
    # لـself_state خالص (نفس ما اتأكد في المراجعة التشخيصية)، فمستحيل "e1"
    # يظهر في health_status_evidence_event_ids حتى لو كان فيه تحذير domain حقيقي.
    diagnosis_evidence = self_state_core._union_evidence([one, zero, zero])
    assert "e1" not in diagnosis_evidence, "e1 (دليل domain) مش المفروض يظهر في أدلة التشخيص خالص"
    assert "e2" in diagnosis_evidence
    print("✅ إثبات بنيوي: أدلة health_status/diagnosis_summary (fallback+rejection+mismatch) مفيهاش أي أثر لدليل domain (e1)")


def test_missing_evidence(monkeypatch_target=None):
    """
    Part B -- فشل قراءة الدليل: لو self_diagnosis نفسه رمى استثناء، النتيجة
    لازم تبقى UNKNOWN/degraded-confidence، مش تتحول افتراضيًا لـ HEALTHY.
    """
    original = self_diagnosis.compute_fallback_count

    def _raise():
        raise RuntimeError("محاكاة فشل قراءة Firestore")

    self_diagnosis.compute_fallback_count = _raise
    try:
        core = self_state_core.compute_self_state_core()
        assert core["health_status"] == "UNKNOWN", core
        assert core["confidence"] in ("degraded", "unknown"), core
        assert core["current_mode"] in ("unknown", "degraded"), core
        assert len(core["computation_errors"]) >= 1
        print(f"✅ فشل قراءة self_diagnosis: health_status=UNKNOWN, confidence={core['confidence']}, current_mode={core['current_mode']} -- مفيش حاجة اتخمّنت")
    finally:
        self_diagnosis.compute_fallback_count = original


def main():
    install_fake_firestore()
    from services.firebase_service import firestore_db

    pre_existing = event_store.get_events_for_entity("self_diagnosis", TEST_ENTITY_ID)
    assert pre_existing == [], f"توقف احترازيًا -- لقيت {len(pre_existing)} حدث اختبار سابق"

    test_pure_functions()
    test_warning_categories()
    test_render_report_no_duplicate_lines()
    test_missing_evidence()

    created_event_ids = []

    try:
        # ============================================================
        # Part C -- قراءة حية (baseline) ضد Firestore الحقيقي
        # ============================================================
        baseline = self_state_core.compute_self_state_core()
        assert baseline["confidence"] == "full", f"المفروض القراءة الحقيقية تنجح بالكامل، لقيت {baseline}"
        print(f"ℹ️ baseline حقيقي: health_status={baseline['health_status']}, current_mode={baseline['current_mode']}, warnings={len(baseline['internal_warnings'])}")

        # ============================================================
        # Part D -- حقن حدث fallback_activation حقيقي واحد، والتأكد إن
        # الدليل بيوصل فعليًا لـ self_state_core (مش عدّاد وهمي)
        # ============================================================
        baseline_fallback = self_diagnosis.compute_fallback_count()
        eid = event_store.record_event(
            entity_type="self_diagnosis", entity_id=TEST_ENTITY_ID,
            attribute="fallback_activation", new_value=True,
            source="test", actor="test_self_state_core",
        )
        created_event_ids.append(eid)

        after = self_state_core.compute_self_state_core()
        after_fallback = self_diagnosis.compute_fallback_count()
        assert after_fallback["count"] == baseline_fallback["count"] + 1
        assert eid in after_fallback["evidence_event_ids"]
        assert after_fallback["explanation"] in after["diagnosis_summary"], (
            f"المفروض تفسير fallback يظهر بالحرف جوه diagnosis_summary، لقيت: {after['diagnosis_summary']!r}"
        )
        print(f"✅ حدث fallback_activation حقيقي واحد وصل فعليًا لـ self_state_core.compute_self_state_core() (evidence_event_id={eid})")

        # تصحيح دلالي 2026-07-27: evidence_event_ids ظاهرة على مستوى الحقل
        # نفسه (health_status/diagnosis_summary)، مش بس متداخلة جوه warnings
        assert eid in after["health_status_evidence_event_ids"], after["health_status_evidence_event_ids"]
        assert eid in after["diagnosis_summary_evidence_event_ids"], after["diagnosis_summary_evidence_event_ids"]
        print(f"✅ evidence_event_ids ظاهرة على مستوى health_status وdiagnosis_summary مباشرة (eid={eid} موجود في الاتنين)")

        # ============================================================
        # Part E -- حقن حدث verbatim_mismatch مباشرة، وتأكيد إن
        # compute_verbatim_mismatch_diagnosis (الدالة الجديدة) بتلقطه صح
        # ============================================================
        baseline_mismatch = self_diagnosis.compute_verbatim_mismatch_diagnosis()
        eid2 = event_store.record_event(
            entity_type="self_diagnosis", entity_id=TEST_ENTITY_ID,
            attribute="verbatim_mismatch", new_value=True,
            source="test", actor="test_self_state_core",
        )
        created_event_ids.append(eid2)

        after_mismatch = self_diagnosis.compute_verbatim_mismatch_diagnosis()
        assert after_mismatch["count"] == baseline_mismatch["count"] + 1
        assert eid2 in after_mismatch["evidence_event_ids"]
        real_event = event_store.get_event(eid2)
        assert real_event is not None and real_event["attribute"] == "verbatim_mismatch"
        print(f"✅ compute_verbatim_mismatch_diagnosis (دالة جديدة): {after_mismatch['count']} (زاد بـ 1 فعليًا)، evidence_event_id يرجع لحدث حقيقي")

        # الوضع الحالي دلوقتي المفروض DEGRADED (mismatch >= 1) مش WATCH بس
        core_now = self_state_core.compute_self_state_core()
        assert core_now["health_status"] == "DEGRADED", core_now
        assert core_now["current_mode"] == "degraded", core_now
        print(f"✅ بعد حقن mismatch حقيقي: health_status=DEGRADED, current_mode=degraded (مش WATCH -- الأولوية صح)")

        # evidence_event_ids ظاهرة برضه على current_mode وconfidence مباشرة
        assert eid2 in core_now["current_mode_evidence_event_ids"], core_now["current_mode_evidence_event_ids"]
        assert eid2 in core_now["confidence_evidence_event_ids"], core_now["confidence_evidence_event_ids"]
        assert eid2 in core_now["health_status_evidence_event_ids"], core_now["health_status_evidence_event_ids"]
        print(f"✅ evidence_event_ids ظاهرة على current_mode وconfidence وhealth_status مباشرة (eid={eid2} موجود في التلاتة)")

        # render_report لسه بيطبع نفس الشكل بالظبط -- "category" و"evidence_event_ids"
        # مش المفروض يظهروا في النص المُوجّه لأحمد خالص (تصنيف داخلي بس)
        rendered = self_state_core.render_report(core_now)
        assert "category" not in rendered and "evidence_event_ids" not in rendered, rendered
        print("✅ render_report لسه بنفس الشكل بالظبط -- category/evidence_event_ids حقول داخلية بس، مش بتسرّب للنص الموجّه لأحمد")

        # ============================================================
        # Part F -- Verbatim Match Validator يفرض تطابق ادّعاء Self State
        # Core بالحرف (Option A -- نفس آلية الأقساط بالظبط)
        # ============================================================
        exact_text = "الحالة: مستقرة\nنص اختبار مُعتمَد لازم يظهر بالحرف."
        verified_expression.register_pending_verification(TEST_CHAT_ID, {
            "text": exact_text, "verified": True, "expression_id": None, "dimension": "self_state_core",
        })
        paraphrased_reply = "تمام يا أحمد، كل حاجة كويسة عندي دلوقتي."
        final = verified_expression.verify_and_finalize(TEST_CHAT_ID, paraphrased_reply)
        assert exact_text in final, f"المفروض النص المعتمد يترجع بالحرف لما الموديل يحاول يعيد الصياغة، لقيت: {final}"
        print(f"✅ إعادة صياغة غير موثقة اترفضت -- النص المعتمد اترجع بالحرف: {final!r}")

        mismatch_events = [
            e for e in event_store.get_events_for_entity("self_diagnosis", "self_state_core")
            if e["attribute"] == "verbatim_mismatch"
        ]
        assert len(mismatch_events) >= 1, "المفروض حدث verbatim_mismatch اتسجل لـ dimension='self_state_core'"
        created_event_ids.extend(e["event_id"] for e in mismatch_events)
        print(f"✅ حدث verbatim_mismatch اتسجل فعليًا لـ entity_id='self_state_core' ({len(mismatch_events)} حدث)")

        # نفس السيناريو، لكن رد فيه النص المعتمد بالحرف -- المفروض يعدي من غير أي تعديل
        verified_expression.register_pending_verification(TEST_CHAT_ID, {
            "text": exact_text, "verified": True, "expression_id": None, "dimension": "self_state_core",
        })
        matching_reply = f"تمام يا أحمد:\n{exact_text}"
        final2 = verified_expression.verify_and_finalize(TEST_CHAT_ID, matching_reply)
        assert final2 == matching_reply, "المفروض الرد يعدي من غير أي تعديل لو فيه النص المعتمد بالحرف فعلًا"
        print("✅ رد فيه النص المعتمد بالحرف فعلًا يعدي من غير أي تصحيح (مفيش false positive)")

        # ============================================================
        # Part G -- Regression: مسار الأقساط (request_verified_expression)
        # لسه شغال بنفس الشكل بعد الـrefactor لـ register_pending_verification
        # ============================================================
        expr = verified_expression.request_verified_expression("tracking_stability", chat_id=TEST_CHAT_ID)
        assert set(expr.keys()) == {"verified", "text", "expression_id"}, expr
        matching = f"بالنسبة لكده: {expr['text']}"
        final3 = verified_expression.verify_and_finalize(TEST_CHAT_ID, matching)
        assert final3 == matching, "المفروض مسار الأقساط لسه شغال زي ما هو -- رد فيه النص بالحرف يعدي من غير تعديل"
        print(f"✅ Regression: request_verified_expression + verify_and_finalize لسه شغالين بنفس الشكل بعد الـrefactor (dimension=tracking_stability)")

    finally:
        for eid in created_event_ids:
            firestore_db.collection(event_store.EVENTS_COLLECTION).document(eid).delete()
        remaining = event_store.get_events_for_entity("self_diagnosis", TEST_ENTITY_ID)
        remaining2 = [
            e for e in event_store.get_events_for_entity("self_diagnosis", "self_state_core")
            if e["attribute"] == "verbatim_mismatch"
        ]
        assert remaining == []
        print(f"🧹 اتمسح {len(created_event_ids)} حدث اختبار (test_self_state_core + self_state_core verbatim_mismatch)")

    print("\n✅✅✅ Self State Core (Health Status, Internal Warnings, Confidence, Current Mode, Diagnosis Summary) شغال فعليًا، بدليل قابل للتتبع بالكامل، وبنفس آلية التحقق بتاعة الأقساط")


if __name__ == "__main__":
    main()
