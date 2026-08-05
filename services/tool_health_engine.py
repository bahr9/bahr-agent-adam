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
from utils.logger import logger

# ============================================================
# عتبات Version 1 -- مؤقتة، موثّقة صراحة (معتمدة 2026-07-27)
# ============================================================
WINDOW_HOURS = 24
MIN_SAMPLE_FOR_HEALTHY = 3          # >= 3 فحص ناجح في 24 ساعة قبل ما نقول HEALTHY
DEGRADED_FAILURE_COUNT = 3          # >= 3 فشل إجمالي (أي مصدر) في 24 ساعة -> DEGRADED
DEGRADED_REPEATED_CAUSE_COUNT = 2   # نفس error_type اتكرر مرتين -> DEGRADED حتى لو الإجمالي أقل

# ============================================================
# حدود القراءة (إصلاح نزيف الكوتا 2026-08-05)
# ============================================================
# سقف صارم لعدد المستندات في أي قراءة واحدة. نافذة 24 ساعة عادية فيها
# 61 أداة × عدد مرات الـ heartbeat -- مئات قليلة. أي رقم قريب من السقف
# ده معناه إن فيه حاجة غلط، مش استخدام طبيعي.
MAX_RECORDS_PER_FETCH = 3000

# هامش قبل حد النافذة في الاستعلام الخام. التواريخ متخزنة كنص ISO بإزاحة
# القاهرة، واللي بتتغير مع التوقيت الصيفي (+02:00 شتاءً / +03:00 صيفًا).
# الهامش بيمنع أي فقد على حدود التحويل، والفلترة الدقيقة بتحصل في بايثون
# بعدها بالظبط زي الأول -- يعني النتيجة النهائية مطابقة تمامًا.
QUERY_MARGIN_HOURS = 3


def _fetch_window(collection_name: str, timestamp_field: str, cutoff: datetime) -> list:
    """يقرا سجلات النافذة الزمنية بس -- مش المجموعة كاملة.

    ليه ده اتغيّر (أوديت 2026-08-05 -- حادثة إنتاج حقيقية):
    الدالة القديمة `_fetch_all` كانت بتعمل `.stream()` على المجموعة **كاملة**
    من غير أي فلتر ولا حد، وتفلتر النافذة في بايثون بعد كده. ومجموعة
    tool_health_checks بتكبر للأبد -- الـ heartbeat بيكتب سجل لكل أداة من
    الـ 61 أداة كل 6 ساعات، ومفيش أي job تنظيف ليها.

    والدالة دي بتتنادى من:
      - فحص الحالة الذاتية كل ساعة (self_state_active_check_job)
      - كل نداء لأداة get_adam_self_state
      - كل نداء لأداة get_tools_health_status
      - الـ heartbeat نفسه

    النتيجة المقيسة يوم 2026-08-05: **53 ألف قراءة مقابل 156 كتابة بس**،
    والكوتا المجانية (50 ألف) خلصت، وآدم اتشل عن أي قراءة من Firestore.

    الفلتر server-side هنا على **حقل واحد** -- ده بيستخدم الـ index التلقائي
    بتاع Firestore ومش محتاج composite index (وده كان سبب تجنّبه أصلاً في
    التعليق القديم).
    """
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []

    query_floor = (cutoff - timedelta(hours=QUERY_MARGIN_HOURS)).isoformat()

    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = (
            firestore_db.collection(collection_name)
            .where(filter=FieldFilter(timestamp_field, ">=", query_floor))
            .limit(MAX_RECORDS_PER_FETCH)
            .stream()
        )
        records = [d.to_dict() for d in docs]
        if len(records) >= MAX_RECORDS_PER_FETCH:
            logger.warning(
                f"⚠️ {collection_name}: وصلنا لسقف {MAX_RECORDS_PER_FETCH} سجل في نافذة "
                f"{QUERY_MARGIN_HOURS + WINDOW_HOURS} ساعة -- يستاهل مراجعة"
            )
        return records
    except Exception as e:
        # الاستعلام المفلتر فشل (حقل ناقص في سجلات قديمة مثلاً).
        # بنرجع لقراءة **محدودة بسقف**، مش المجموعة كاملة -- أسوأ حالة
        # نتيجة أقل دقة، مش نزيف كوتا تاني.
        logger.warning(
            f"⚠️ استعلام النافذة فشل على {collection_name} ({timestamp_field}) -- "
            f"رجعت لقراءة محدودة بـ {MAX_RECORDS_PER_FETCH}: {e}"
        )
        try:
            return [
                d.to_dict() for d in
                firestore_db.collection(collection_name).limit(MAX_RECORDS_PER_FETCH).stream()
            ]
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

    # قراءة النافذة بس -- الحقول الزمنية مختلفة بين المجموعتين
    all_checks = _fetch_window(TOOL_HEALTH_CHECKS_COLLECTION, "checked_at", cutoff)
    all_failures = _fetch_window(TOOL_FAILURES_LOG_COLLECTION, "failed_at", cutoff)

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
