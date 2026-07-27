# -*- coding: utf-8 -*-
"""
Tests First -- Runtime Capabilities & Tool Health V1.

نفس منهجية باقي اختبارات المشروع: تشغيل فعلي (مش نظري)، بعضها وحدات نقية
(صفر Firestore، صفر تكلفة)، وبعضها تكامل حقيقي ضد Firestore الحي (بيانات
اختبار محقونة بأسماء أدوات وهمية مميزة زي "test_tool_health_fake_tool" --
مش أسماء أدوات حقيقية، عشان محدش يفتكرها Capability فعلية -- وبتتمسح بعد
التأكيد). صفر استدعاء LLM في الملف ده -- كل حاجة هنا حتمية بحتة.

**صفر مساس ببيانات عمل حقيقية**: مفيش اختبار هنا بيستدعي loan_record_installment
أو أي أداة كتابة/حذف حقيقية. الـheartbeat نفسه (بيتشغّل فعليًا هنا) بيشغّل
بس safe_probes (قراءة بحتة، مؤكدة سلفًا في capabilities_registry.py).
"""

from services.firebase_service import init_firebase
from services import (
    capabilities_registry, tool_health_heartbeat, tool_health_engine,
    tool_health_alerts, tool_failure_observer, self_state_core, event_store,
    verified_expression,
)
from services.claude_service import _execute_tool

FAKE_TOOL = "test_tool_health_fake_tool"
TEST_CHAT_ID = 999002


# ============================================================
# Part A -- Registry: alignment + drift detection (صفر Firestore)
# ============================================================

def test_registry_alignment_and_drift():
    drift = capabilities_registry.check_drift()
    assert drift["missing_from_metadata"] == [], f"أدوات حقيقية بدون تصنيف: {drift['missing_from_metadata']}"
    assert drift["stale_in_metadata"] == [], f"تصنيفات لأدوات مش موجودة فعليًا: {drift['stale_in_metadata']}"
    print("✅ Registry متطابق 100% مع claude_service.TOOLS الحقيقية -- صفر انحراف")

    # محاكاة انحراف صناعي -- نتأكد إن الفحص فعلاً بيمسك الحالتين، مش بس بيرجع فاضي دايمًا
    import services.capabilities_registry as reg_module
    original = dict(reg_module._TOOL_METADATA)
    try:
        reg_module._TOOL_METADATA["a_tool_that_does_not_exist"] = {"domain": "x"}
        del reg_module._TOOL_METADATA["get_weather"]  # نشيل واحدة حقيقية مؤقتًا
        drift2 = reg_module.check_drift()
        assert "a_tool_that_does_not_exist" in drift2["stale_in_metadata"]
        assert "get_weather" in drift2["missing_from_metadata"]
        print("✅ فحص الانحراف بيمسك فعليًا (stale + missing) لما فيه انحراف صناعي حقيقي")
    finally:
        reg_module._TOOL_METADATA.clear()
        reg_module._TOOL_METADATA.update(original)

    # كل الأدوات اللي عندها health_check_supported لازم يكون operation_type
    # بتاعها "read" أو "analysis" -- صفر أداة كتابة/حذف عندها safe_probe خالص
    registry = capabilities_registry.get_registry()
    for name, meta in registry.items():
        if meta.get("health_check_supported"):
            assert meta["operation_type"] in ("read", "analysis"), (
                f"{name}: عندها safe_probe لكن operation_type={meta['operation_type']} -- ده خرق لقاعدة الأمان"
            )
    print("✅ صفر أداة write/delete عندها safe_probe في الـ Registry")


# ============================================================
# Part B -- Heartbeat mechanics: success/failure/timeout (صفر Firestore)
# ============================================================

def test_heartbeat_timeout_mechanics():
    def _instant_ok():
        return {"ok": True}

    def _raises():
        raise ValueError("محاكاة فشل حقيقي")

    def _hangs():
        import time as _t
        _t.sleep(2)

    outcome, error_type, summary = tool_health_heartbeat._run_with_timeout(_instant_ok, timeout_ms=1000)
    assert outcome == "success" and error_type is None
    print("✅ heartbeat: probe سريع وناجح -> success")

    outcome, error_type, summary = tool_health_heartbeat._run_with_timeout(_raises, timeout_ms=1000)
    assert outcome == "failure" and error_type == "ValueError"
    print("✅ heartbeat: probe رمى استثناء -> failure, error_type محفوظ صح")

    outcome, error_type, summary = tool_health_heartbeat._run_with_timeout(_hangs, timeout_ms=200)
    assert outcome == "timeout" and error_type == "TimeoutError"
    print("✅ heartbeat: probe تجاوز الحد الزمني -> timeout")


# ============================================================
# Part C -- Sanitization (صفر Firestore)
# ============================================================

def test_error_sanitization():
    long_msg = "x" * 500 + " secret_token=ABCDEF123456"
    error_type, summary = tool_failure_observer.sanitize_error(ValueError(long_msg))
    assert error_type == "ValueError"
    assert len(summary) <= tool_failure_observer.MAX_ERROR_SUMMARY_LENGTH
    print(f"✅ sanitize_error: النوع محفوظ (ValueError)، الرسالة مقصوصة لطول {len(summary)} <= {tool_failure_observer.MAX_ERROR_SUMMARY_LENGTH}")


# ============================================================
# Part D -- Deterministic classification: كل الحالات الخمسة (صفر Firestore)
# ============================================================

def test_classification_all_states():
    supported_meta = {"health_check_supported": True, "safe_probe": lambda: None}
    unsupported_meta = {"health_check_supported": False, "safe_probe": None}

    # HEALTHY: >= 3 فحص ناجح، صفر فشل
    checks = [{"result": "success", "evidence_event_id": f"e{i}"} for i in range(3)]
    r = tool_health_engine._classify_one("t", supported_meta, checks, [])
    assert r["status"] == "HEALTHY", r
    assert len(r["evidence_event_ids"]) == 3

    # UNKNOWN: أقل من 3 فحص ناجح، صفر فشل (عيّنة ناقصة)
    r = tool_health_engine._classify_one("t", supported_meta, checks[:1], [])
    assert r["status"] == "UNKNOWN", r

    # UNKNOWN: صفر فحص خالص (مفيش دليل أصلًا)
    r = tool_health_engine._classify_one("t", supported_meta, [], [])
    assert r["status"] == "UNKNOWN", r

    # NOT_MONITORED: مفيش probe، صفر فشل حقيقي
    r = tool_health_engine._classify_one("t", unsupported_meta, [], [])
    assert r["status"] == "NOT_MONITORED", r

    # WATCH: فشل واحد بس، بدون نمط متكرر
    failures = [{"error_type": "ConnectionError", "evidence_event_id": "f1"}]
    r = tool_health_engine._classify_one("t", supported_meta, [], failures)
    assert r["status"] == "WATCH", r

    # DEGRADED عبر العدد الإجمالي (>= 3 فشل، أسباب مختلفة)
    failures3 = [
        {"error_type": "A", "evidence_event_id": "f1"},
        {"error_type": "B", "evidence_event_id": "f2"},
        {"error_type": "C", "evidence_event_id": "f3"},
    ]
    r = tool_health_engine._classify_one("t", supported_meta, [], failures3)
    assert r["status"] == "DEGRADED", r

    # DEGRADED عبر نمط سبب متكرر (نفس error_type مرتين، إجمالي أقل من 3)
    repeated = [
        {"error_type": "ConnectionError", "evidence_event_id": "f1"},
        {"error_type": "ConnectionError", "evidence_event_id": "f2"},
    ]
    r = tool_health_engine._classify_one("t", supported_meta, [], repeated)
    assert r["status"] == "DEGRADED", r
    assert r["detail"]["by_cause"]["ConnectionError"] == 2

    # NOT_MONITORED مع فشل حقيقي (بدون probe) -- لازم برضه يتصنّف من الفشل الحقيقي، مش يفضل NOT_MONITORED
    r = tool_health_engine._classify_one("t", unsupported_meta, [], failures)
    assert r["status"] == "WATCH", r
    print("✅ كل الحالات الخمسة (HEALTHY/WATCH/DEGRADED×2/UNKNOWN×2/NOT_MONITORED) + فشل حقيقي بدون probe صح")


# ============================================================
# Part E -- Alert dedup / cooldown / recovery (Firestore حقيقي، أداة وهمية)
# ============================================================

def test_alerting_dedup_cooldown_recovery():
    from services.firebase_service import firestore_db
    from config import TOOL_HEALTH_ALERT_STATE_COLLECTION
    from datetime import timedelta
    from utils.time_utils import now_cairo

    doc_ref = firestore_db.collection(TOOL_HEALTH_ALERT_STATE_COLLECTION).document(FAKE_TOOL)
    doc_ref.delete()  # تنظيف احترازي لو فيه أثر سابق

    try:
        sent_messages = []
        send_fn = lambda text: sent_messages.append(text)

        degraded_a = {FAKE_TOOL: {"status": "DEGRADED", "evidence_event_ids": [], "detail": {"by_cause": {"ConnectionError": 3}}}}

        # أول مرة تدخل DEGRADED -- لازم تنبيه
        sent = tool_health_alerts.maybe_alert(degraded_a, send_fn)
        assert len(sent) == 1 and sent[0]["kind"] == "entered_degraded"
        print("✅ دخول DEGRADED لأول مرة -> تنبيه اتبعت")

        # نفس الحالة تاني فورًا -- مفروض صفر تنبيه (dedup + cooldown)
        sent2 = tool_health_alerts.maybe_alert(degraded_a, send_fn)
        assert sent2 == []
        print("✅ نفس حالة DEGRADED (نفس السبب) فورًا تاني -> صفر تنبيه إضافي (dedup)")

        # نفس الحالة DEGRADED بس السبب اتغيّر -- المفروض برضه صفر تنبيه دلوقتي (cooldown لسه فعّال)
        degraded_b = {FAKE_TOOL: {"status": "DEGRADED", "evidence_event_ids": [], "detail": {"by_cause": {"TimeoutError": 3}}}}
        sent3 = tool_health_alerts.maybe_alert(degraded_b, send_fn)
        assert sent3 == []
        print("✅ سبب اتغيّر لكن جوه فترة الـcooldown -> صفر تنبيه (الـcooldown بيمنع الإزعاج الزيادة)")

        # نلف الساعة للخلف يدويًا (نمحي last_alerted_at) عشان نتخطى الـcooldown ونتأكد إن تغيّر
        # السبب فعليًا كان هيولّد تنبيه لولا الـcooldown
        doc_ref.set({"last_alerted_at": (now_cairo() - timedelta(hours=2)).isoformat()}, merge=True)
        sent4 = tool_health_alerts.maybe_alert(degraded_b, send_fn)
        assert len(sent4) == 1 and sent4[0]["kind"] == "cause_changed"
        print("✅ بعد انتهاء الـcooldown: تغيّر السبب الغالب -> تنبيه 'cause_changed' اتبعت")

        # تعافي: من DEGRADED لـHEALTHY -- تنبيه recovery (بعد تخطي الـcooldown تاني)
        doc_ref.set({"last_alerted_at": (now_cairo() - timedelta(hours=2)).isoformat()}, merge=True)
        healthy = {FAKE_TOOL: {"status": "HEALTHY", "evidence_event_ids": [], "detail": {}}}
        sent5 = tool_health_alerts.maybe_alert(healthy, send_fn)
        assert len(sent5) == 1 and sent5[0]["kind"] == "recovered"
        print("✅ تعافي من DEGRADED لـHEALTHY -> تنبيه 'recovered' اتبعت")

        # بعد التعافي، تكرار HEALTHY -- صفر تنبيه (مفيش تنبيه لكل فحص سليم)
        sent6 = tool_health_alerts.maybe_alert(healthy, send_fn)
        assert sent6 == []
        print("✅ استمرار HEALTHY بعد التعافي -> صفر تنبيه إضافي")

    finally:
        doc_ref.delete()
        print("🧹 اتمسحت حالة التنبيه الوهمية")


# ============================================================
# Part F -- Deterministic report rendering (صفر Firestore)
# ============================================================

def test_deterministic_report():
    evaluations = {
        "a": {"status": "HEALTHY", "evidence_event_ids": ["e1"], "detail": {}},
        "b": {"status": "DEGRADED", "evidence_event_ids": ["e2"], "detail": {}},
    }
    r1 = tool_health_engine.render_health_report(evaluations)
    r2 = tool_health_engine.render_health_report(evaluations)
    assert r1 == r2, "المفروض نفس المدخلات تدّي نفس النص بالظبط -- صفر عشوائية"
    assert "b" in r1 and "DEGRADED" in r1
    print("✅ render_health_report حتمي (نفس المدخلات = نفس النص) وبيوضح الأداة المتدهورة")


def main():
    assert init_firebase(), "فشل الاتصال بـ Firebase"

    test_registry_alignment_and_drift()
    test_heartbeat_timeout_mechanics()
    test_error_sanitization()
    test_classification_all_states()
    test_deterministic_report()
    test_alerting_dedup_cooldown_recovery()

    created_event_ids = []
    from services.firebase_service import firestore_db
    from config import TOOL_FAILURES_LOG_COLLECTION, TOOL_HEALTH_CHECKS_COLLECTION

    try:
        # ============================================================
        # Part G -- Centralized real-use failure observer (Firestore حقيقي)
        # ============================================================
        pre_existing = event_store.get_events_for_entity("tool_health", FAKE_TOOL)
        assert pre_existing == [], f"توقف احترازيًا -- لقيت {len(pre_existing)} حدث اختبار سابق"

        tool_failure_observer.record_tool_failure(FAKE_TOOL, KeyError("محاكاة"), chat_id=TEST_CHAT_ID, latency_ms=42)

        events = event_store.get_events_for_entity("tool_health", FAKE_TOOL)
        assert len(events) == 1 and events[0]["attribute"] == "real_use_failure"
        created_event_ids.append(events[0]["event_id"])
        print(f"✅ record_tool_failure سجّل حدث Event Store حقيقي (attribute=real_use_failure)")

        failure_docs = list(firestore_db.collection(TOOL_FAILURES_LOG_COLLECTION).where("tool_name", "==", FAKE_TOOL).stream())
        assert len(failure_docs) == 1
        fdoc = failure_docs[0].to_dict()
        assert fdoc["execution_source"] == "real_use"
        assert fdoc["error_type"] == "KeyError"
        assert fdoc["evidence_event_id"] == events[0]["event_id"]
        print("✅ tool_failures_log فيه سجل حقيقي مرتبط بنفس evidence_event_id -- execution_source='real_use' صريح")

        # ============================================================
        # Part H -- فصل heartbeat عن real_use + الأدوات الحقيقية غير المُراقَبة
        # ============================================================
        real_evaluations = tool_health_engine.evaluate_all_tools()
        assert real_evaluations["loan_record_installment"]["status"] == "NOT_MONITORED", (
            "أداة كتابة حقيقية (loan_record_installment) بدون safe_probe ومن غير فشل حقيقي عليها "
            "لازم تفضل NOT_MONITORED"
        )
        print("✅ loan_record_installment (أداة كتابة حقيقية بدون safe_probe) مصنّفة NOT_MONITORED فعليًا")

        checks_docs = list(firestore_db.collection(TOOL_HEALTH_CHECKS_COLLECTION).where("tool_name", "==", FAKE_TOOL).stream())
        assert checks_docs == [], "المفروض صفر heartbeat check لأداة وهمية -- الـheartbeat ماينفعش يشتغل على أداة مش حقيقية"
        print("✅ فشل حقيقي (real_use) وفشل heartbeat محفوظين في collections مختلفة تمامًا -- الفصل صريح على مستوى البيانات")

        # ============================================================
        # Part I -- Verified-expression delivery لتقرير صحة الأدوات (Option A)
        # ============================================================
        exact_text = "تقرير اختبار صحة الأدوات -- نص مُعتمَد لازم يظهر بالحرف."
        verified_expression.register_pending_verification(TEST_CHAT_ID, {
            "text": exact_text, "verified": True, "expression_id": None, "dimension": "tool_health",
        })
        paraphrased = "الأدوات شكلها تمام يا أحمد."
        final = verified_expression.verify_and_finalize(TEST_CHAT_ID, paraphrased)
        assert exact_text in final, final
        print("✅ إعادة صياغة غير موثقة لتقرير صحة الأدوات اترفضت -- النص المعتمد اترجع بالحرف")

        mismatch_events = [
            e for e in event_store.get_events_for_entity("self_diagnosis", "tool_health")
            if e["attribute"] == "verbatim_mismatch"
        ]
        created_event_ids.extend(e["event_id"] for e in mismatch_events)

        # ============================================================
        # Part J -- تكامل Self State Core (تحذيرات فقط، health_status ثابتة)
        # ============================================================
        core = self_state_core.compute_self_state_core()
        assert core["confidence"] in ("full", "degraded", "unknown")
        tool_health_warnings_present = [w for w in core["internal_warnings"] if w["source"].startswith("tool_health:")]
        for w in tool_health_warnings_present:
            assert w["category"] == "runtime", w
        print(f"✅ Self State Core لسه بيرجع نتيجة سليمة، وأي تحذير tool_health (لقينا {len(tool_health_warnings_present)}) category=runtime صح")

        # إثبات بنيوي: health_status_evidence_event_ids ماعندهوش أي أثر لحدث tool_health
        for eid in core["health_status_evidence_event_ids"]:
            ev = event_store.get_event(eid)
            if ev:
                assert ev["entity"]["type"] == "self_diagnosis", (
                    f"health_status_evidence_event_ids فيها دليل من entity_type={ev['entity']['type']} -- "
                    "المفروض self_diagnosis بس، صفر tool_health"
                )
        print("✅ health_status_evidence_event_ids نضيفة من أي دليل tool_health -- health_status لسه مقصورة على خط أنابيب التعبير بس")

        # ============================================================
        # Part K -- Regression: dispatch الحقيقي + Loans + Self State Core الأساسي
        # ============================================================
        result = _execute_tool("list_graph_nodes", {}, TEST_CHAT_ID)
        assert isinstance(result, str) and "خطأ" not in result[:20]
        print("✅ Regression: _execute_tool (dispatch الحقيقي) لسه شغال زي ما هو بعد إضافة الـobserver hook")

        expr = verified_expression.request_verified_expression("tracking_stability", chat_id=TEST_CHAT_ID)
        assert set(expr.keys()) == {"verified", "text", "expression_id"}
        final_loans = verified_expression.verify_and_finalize(TEST_CHAT_ID, f"تمام: {expr['text']}")
        assert final_loans == f"تمام: {expr['text']}"
        print("✅ Regression: مسار الأقساط (request_verified_expression + verify_and_finalize) لسه سليم")

    finally:
        for eid in created_event_ids:
            firestore_db.collection(event_store.EVENTS_COLLECTION).document(eid).delete()
        for doc in firestore_db.collection(TOOL_FAILURES_LOG_COLLECTION).where("tool_name", "==", FAKE_TOOL).stream():
            doc.reference.delete()
        remaining = event_store.get_events_for_entity("tool_health", FAKE_TOOL)
        assert remaining == []
        print(f"🧹 اتمسح كل بيانات الاختبار المرتبطة بـ {FAKE_TOOL} والتحقق المؤقت")

    print("\n✅✅✅ Runtime Capabilities & Tool Health V1 شغالة فعليًا -- Registry بدون انحراف، heartbeat آمن، "
          "engine حتمي بكل الحالات الخمسة، alerting بـdedup/cooldown/recovery، تسليم عبر verified-expression، "
          "تكامل Self State Core بدون مساس بـ health_status، وصفر regression في الأقساط أو الـdispatch الحقيقي.")


if __name__ == "__main__":
    main()
