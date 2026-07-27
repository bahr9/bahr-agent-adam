# -*- coding: utf-8 -*-
"""
💓 Safe Heartbeat Monitoring -- Runtime Capabilities & Tool Health V1
=====================================================
بيشغّل *بس* الأدوات اللي عندها safe_probe مُعتمَد صراحة في
services/capabilities_registry.py (health_check_supported=True). قاعدة
حاكمة صارمة: **مفيش استدعاء أعمى لأي أداة**. أي أداة كتابة/حذف من غير probe
مستقل read-only بترجع NOT_MONITORED من tool_health_engine.py -- الملف ده
مايحاولش يستدعيها أصلًا.

كل probe بيتشغّل جوه thread منفصل مع timeout حقيقي (مأخوذ من الـ Registry،
timeout_ms لكل أداة) -- الـ SDK بتاع Firestore synchronous بحت، فده الطريقة
القياسية في بايثون لفرض حد زمني على استدعاء متزامن. لو الـ thread فضل حي
بعد الـ timeout، النتيجة "timeout" -- الـ thread نفسه بيتسيب يخلص لوحده
(بايثون مقدرش يقفل thread بالقوة)، ده حد معروف موثّق، مش باگ.

كل نتيجة بتتسجل في مكانين مربوطين ببعض (نفس نمط StateSnapshot+Expression):
  1. حدث Event Store (entity_type="tool_health", attribute="heartbeat_check")
     -- الدليل الخام القابل للتتبع.
  2. سجل في Firestore collection "tool_health_checks" -- شكل منظم للاستعلام
     السريع (كل الفحوصات لأداة معيّنة، آخر فحص لكل أداة، إلخ)، فيه
     evidence_event_id بيشاور على (1).

صفر LLM هنا. صفر جانب-تأثير على أي بيانات عمل حقيقية -- كل الـsafe_probes
دوال قراءة بحتة (مؤكدة في capabilities_registry.py).
"""

import threading
import time

from services import event_store, capabilities_registry, tool_failure_observer
from config import TOOL_HEALTH_CHECKS_COLLECTION
from utils.time_utils import now_cairo
from utils.logger import logger

PROBE_VERSION = "v1"


def _run_with_timeout(probe, timeout_ms: int):
    """
    يشغّل probe (دالة صفر باراميتر) جوه thread، بيرجع (outcome, error_type, summary).
    outcome ∈ {"success", "failure", "timeout"}.
    """
    result_holder = {}
    error_holder = {}

    def _target():
        try:
            result_holder["value"] = probe()
        except Exception as e:
            error_holder["error"] = e

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout_ms / 1000.0)

    if thread.is_alive():
        return "timeout", "TimeoutError", f"تجاوز الحد الزمني المسموح ({timeout_ms}ms)"

    if "error" in error_holder:
        error_type, summary = tool_failure_observer.sanitize_error(error_holder["error"])
        return "failure", error_type, summary

    return "success", None, None


def _record_check(tool_name: str, outcome: str, latency_ms: int, error_type, summary) -> None:
    """يسجّل حدث Event Store + سجل tool_health_checks مربوطين ببعض، best-effort بالكامل."""
    try:
        event_id = event_store.record_event(
            entity_type="tool_health",
            entity_id=tool_name,
            attribute="heartbeat_check",
            new_value={"result": outcome, "error_type": error_type},
            source="system",
            actor="tool_health_heartbeat",
        )

        from services.firebase_service import firestore_db
        if firestore_db is not None:
            firestore_db.collection(TOOL_HEALTH_CHECKS_COLLECTION).document().set({
                "tool_name": tool_name,
                "checked_at": now_cairo().isoformat(),
                "result": outcome,
                "latency_ms": latency_ms,
                "error_type": error_type,
                "sanitized_error_summary": summary,
                "probe_version": PROBE_VERSION,
                "evidence_event_id": event_id,
            })
    except Exception as e:
        logger.error(f"❌ فشل تسجيل tool_health_checks لـ {tool_name} (مش حرج): {e}")


def run_heartbeat() -> dict:
    """
    نقطة الدخول الوحيدة -- بتتنادى من main.py مرة كل ساعة (نفس نمط
    self_state_active_check_job). بترجع {tool_name: {"result":..., "latency_ms":...}}
    -- بس للأدوات اللي عندها safe_probe فعلي، صفر استدعاء لأي أداة تانية.
    """
    registry = capabilities_registry.get_registry()
    results = {}

    for tool_name, meta in registry.items():
        if not (meta.get("health_check_supported") and meta.get("safe_probe")):
            continue

        start = time.time()
        outcome, error_type, summary = _run_with_timeout(meta["safe_probe"], meta.get("timeout_ms", 5000))
        latency_ms = int((time.time() - start) * 1000)

        _record_check(tool_name, outcome, latency_ms, error_type, summary)
        results[tool_name] = {"result": outcome, "latency_ms": latency_ms, "error_type": error_type}

        logger.info(f"💓 heartbeat[{tool_name}]: {outcome} ({latency_ms}ms)")

    return results
