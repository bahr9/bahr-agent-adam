# -*- coding: utf-8 -*-
"""
🩺 Tool Health Engine V1 -- Runtime Capabilities & Tool Health V1
=====================================================
محرك حتمي بحت -- صفر LLM، صفر baseline متكيّف/متعلّم. عتبات V1 صريحة
موثّقة (مؤقتة، مش حقيقة معمارية دائمة -- زي عتبات Self State Core بالحرف).
أي تعديل مستقبلي محتاج مراجعة وتوثيق صريح، مش تغيير صامت.

يقرأ 3 مصادر بس: tool_health_checks (heartbeat)، tool_failures_log
(real_use)، وservices/capabilities_registry.py (هل الأداة عندها safe_probe
أصلًا). صفر تخزين لنتيجة التصنيف نفسها -- بتتحسب "on the fly" كل مرة، نفس
مبدأ self_state_engine.compute_self_state().

الحالات الخمسة:
  HEALTHY        : دليل نجاح كافٍ (>= MIN_SAMPLE_FOR_HEALTHY فحص ناجح في
                    24 ساعة)، وصفر فشل مسجّل خلال نفس النافذة.
  WATCH          : فشل واحد لحد اتنين، بدون نمط سبب متكرر ولا عدد كافٍ لـ DEGRADED.
  DEGRADED       : (أ) >= DEGRADED_FAILURE_COUNT فشل إجمالي (heartbeat +
                    real_use سوا) في 24 ساعة، أو (ب) نفس error_type اتكرر
                    >= DEGRADED_REPEATED_CAUSE_COUNT مرة (نمط سبب متكرر،
                    حتى لو العدد الإجمالي أقل من عتبة (أ)).
  UNKNOWN        : الأداة عندها safe_probe لكن مفيش دليل كافٍ لسه (مفيش
                    فحوصات خالص، أو فحوصات ناجحة أقل من MIN_SAMPLE_FOR_HEALTHY
                    وصفر فشل -- عيّنة ناقصة، مش "healthy بالتخمين").
  NOT_MONITORED  : مفيش safe_probe أصلًا، وصفر دليل فشل حقيقي (real_use) في
                    النافذة -- الحالة الافتراضية الصحيحة لمعظم أدوات
                    الكتابة/الحذف. **مش يُصنَّف "فشل" لمجرد غياب probe.**

ملاحظة حاسمة: أداة من غير safe_probe لكن **عندها** فشل real_use حقيقي
مسجّل بتتصنّف WATCH/DEGRADED زي أي أداة تانية -- غياب الـprobe مايمنعش
الدليل الحقيقي من التأثير، هو بس مايخترعش دليل ناجح مش موجود.
"""

from datetime import datetime, timedelta

from services import capabilities_registry
from config import TOOL_HEALTH_CHECKS_COLLECTION, TOOL_FAILURES_LOG_COLLECTION
from utils.time_utils import now_cairo

# ============================================================
# عتبات Version 1 -- مؤقتة، موثّقة صراحة (معتمدة 2026-07-27)
# ============================================================
WINDOW_HOURS = 24
MIN_SAMPLE_FOR_HEALTHY = 3          # >= 3 فحص ناجح في 24 ساعة قبل ما نقول HEALTHY
DEGRADED_FAILURE_COUNT = 3          # >= 3 فشل إجمالي (أي مصدر) في 24 ساعة -> DEGRADED
DEGRADED_REPEATED_CAUSE_COUNT = 2   # نفس error_type اتكرر مرتين -> DEGRADED حتى لو الإجمالي أقل


def _fetch_all(collection_name: str) -> list:
    """قراءة كل السجلات في collection معيّن -- فلترة النافذة الزمنية بتحصل بعد كده في بايثون
    (نفس نمط self_diagnosis.py -- تجنّب الحاجة لـ composite index في Firestore)."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []
    try:
        return [d.to_dict() for d in firestore_db.collection(collection_name).stream()]
    except Exception:
        return []


def _within_window(iso_ts: str, cutoff: datetime) -> bool:
    try:
        return datetime.fromisoformat(iso_ts) >= cutoff
    except Exception:
        return False


def _classify_one(tool_name: str, meta: dict, checks: list, failures: list) -> dict:
    health_check_supported = bool(meta.get("health_check_supported") and meta.get("safe_probe"))

    failure_events = []
    for c in checks:
        if c.get("result") in ("failure", "timeout"):
            failure_events.append({
                "source": "heartbeat", "error_type": c.get("error_type"),
                "evidence_event_id": c.get("evidence_event_id"),
            })
    for f in failures:
        failure_events.append({
            "source": "real_use", "error_type": f.get("error_type"),
            "evidence_event_id": f.get("evidence_event_id"),
        })

    failures_total = len(failure_events)
    by_cause = {}
    for fe in failure_events:
        cause = fe.get("error_type") or "unknown"
        by_cause[cause] = by_cause.get(cause, 0) + 1
    repeated_cause_count = max(by_cause.values()) if by_cause else 0
    failure_evidence_ids = [fe["evidence_event_id"] for fe in failure_events if fe.get("evidence_event_id")]

    if failures_total == 0:
        if health_check_supported:
            successes = [c for c in checks if c.get("result") == "success"]
            if len(successes) >= MIN_SAMPLE_FOR_HEALTHY:
                return {
                    "status": "HEALTHY",
                    "evidence_event_ids": [c["evidence_event_id"] for c in successes if c.get("evidence_event_id")],
                    "detail": {"successful_checks": len(successes)},
                }
            return {
                "status": "UNKNOWN",
                "evidence_event_ids": [c["evidence_event_id"] for c in checks if c.get("evidence_event_id")],
                "detail": {"reason": "insufficient_sample", "successful_checks": len(successes)},
            }
        return {"status": "NOT_MONITORED", "evidence_event_ids": [], "detail": {"reason": "no_safe_probe_no_failures"}}

    if repeated_cause_count >= DEGRADED_REPEATED_CAUSE_COUNT or failures_total >= DEGRADED_FAILURE_COUNT:
        return {
            "status": "DEGRADED",
            "evidence_event_ids": failure_evidence_ids,
            "detail": {"failures_total": failures_total, "by_cause": by_cause},
        }

    return {
        "status": "WATCH",
        "evidence_event_ids": failure_evidence_ids,
        "detail": {"failures_total": failures_total, "by_cause": by_cause},
    }


def evaluate_all_tools(window_hours: int = WINDOW_HOURS) -> dict:
    """
    يرجع {tool_name: {"status", "evidence_event_ids", "detail"}} لكل أداة
    حقيقية في الـ Registry (مشتقة حصريًا من claude_service.TOOLS). فحص
    حتمي، صفر LLM، صفر baseline متعلّم.
    """
    cutoff = now_cairo() - timedelta(hours=window_hours)
    registry = capabilities_registry.get_registry()

    all_checks = _fetch_all(TOOL_HEALTH_CHECKS_COLLECTION)
    all_failures = _fetch_all(TOOL_FAILURES_LOG_COLLECTION)

    checks_by_tool = {}
    for c in all_checks:
        if _within_window(c.get("checked_at", ""), cutoff):
            checks_by_tool.setdefault(c.get("tool_name"), []).append(c)

    failures_by_tool = {}
    for f in all_failures:
        if _within_window(f.get("failed_at", ""), cutoff):
            failures_by_tool.setdefault(f.get("tool_name"), []).append(f)

    return {
        tool_name: _classify_one(
            tool_name, meta,
            checks_by_tool.get(tool_name, []),
            failures_by_tool.get(tool_name, []),
        )
        for tool_name, meta in registry.items()
    }


def get_tool_health_warnings() -> list:
    """
    للتكامل مع Self State Core (قسم 7 من المهمة) -- بترجع بس أدوات WATCH/DEGRADED
    كتحذيرات evidence-backed، category="runtime" (أبدًا "domain"). لا تُستخدم
    من هنا لتغيير معنى health_status الحالي (المقصور على موثوقية خط أنابيب
    التعبير) -- قرار تأجيل الدمج موثّق صراحة في RUNTIME_TOOL_HEALTH_V1.md.
    """
    evaluations = evaluate_all_tools()
    warnings = []
    for tool_name, ev in evaluations.items():
        if ev["status"] in ("WATCH", "DEGRADED"):
            warnings.append({
                "source": f"tool_health:{tool_name}",
                "category": "runtime",
                "level": ev["status"],
                "evidence_event_ids": ev["evidence_event_ids"],
                "explanation": f"الأداة '{tool_name}' في حالة {ev['status']} -- {ev['detail']}",
            })
    return warnings


def render_health_report(evaluations: dict = None) -> str:
    """
    نص عربي حتمي واحد -- بيتسجل كـ pending verification (Option A) ويترجع
    للموديل. صفر LLM هنا، صفر صياغة حرة -- تجميع نصي بحت من النتائج المحسوبة.
    """
    if evaluations is None:
        evaluations = evaluate_all_tools()

    by_status = {"HEALTHY": [], "WATCH": [], "DEGRADED": [], "UNKNOWN": [], "NOT_MONITORED": []}
    for tool_name, ev in evaluations.items():
        by_status[ev["status"]].append(tool_name)

    lines = [f"تقرير صحة الأدوات (آخر {WINDOW_HOURS} ساعة):"]
    lines.append(f"- سليمة (HEALTHY): {len(by_status['HEALTHY'])}")
    lines.append(f"- تحت المراقبة (WATCH): {len(by_status['WATCH'])}" + (f" -- {', '.join(by_status['WATCH'])}" if by_status['WATCH'] else ""))
    lines.append(f"- متدهورة (DEGRADED): {len(by_status['DEGRADED'])}" + (f" -- {', '.join(by_status['DEGRADED'])}" if by_status['DEGRADED'] else ""))
    lines.append(f"- غير معروفة (UNKNOWN): {len(by_status['UNKNOWN'])}" + (f" -- {', '.join(by_status['UNKNOWN'])}" if by_status['UNKNOWN'] else ""))
    lines.append(f"- غير مُراقَبة (NOT_MONITORED): {len(by_status['NOT_MONITORED'])}")

    evidence_ids = sorted({eid for ev in evaluations.values() for eid in ev["evidence_event_ids"]})
    if evidence_ids:
        lines.append(f"عدد أدلة الأحداث المرجعية: {len(evidence_ids)}")

    return "\n".join(lines)
