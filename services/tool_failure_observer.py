# -*- coding: utf-8 -*-
"""
🩹 Tool Failure Observer -- Runtime Capabilities & Tool Health V1
=====================================================
ملاحظة مركزية لفشل حقيقي بيحصل أثناء تنفيذ فعلي لأداة (execution_source=
"real_use") -- من نقطة الاعتراض المشتركة الوحيدة (claude_service._execute_tool's
except block)، مش متفرقة على كل أداة لوحدها. بتسجل في Firestore
(tool_failures_log) + حدث Event Store مقابل (evidence_event_id) -- نفس نمط
StateSnapshot+Expression في verified_expression.py (تسجيل منفصل + ربط بالـ ID).

**صفر تغيير في سلوك معالجة الخطأ الأصلي.** الدالة دي best-effort بحتة تمامًا
-- أي فشل فيها (حتى فشل الكتابة في Firestore نفسها) بيتسجل في اللوج المحلي
بس ومايتصعّدش أبدًا، فمايأثرش على الرسالة اللي بترجع لأحمد (نفس فلسفة
_shadow_run_pipeline في verified_expression.py -- الضمانة الوحيدة اللي
لازم تفضل قايمة هي رجوع رسالة الخطأ الأصلية زي ما هي بالظبط).

**صفر بيانات حساسة تتخزن هنا:** مفيش tool_input خام، مفيش رسالة أحمد
الكاملة، مفيش stack trace خام -- بس نوع الاستثناء (error_type) ورسالته
مختصرة لطول محدود (sanitized_error_summary).
"""

from services import event_store
from config import TOOL_FAILURES_LOG_COLLECTION
from utils.time_utils import now_cairo
from utils.logger import logger

MAX_ERROR_SUMMARY_LENGTH = 200


def sanitize_error(exc: Exception) -> tuple:
    """(error_type, sanitized_summary) -- صفر stack trace خام، صفر أسرار. النوع + رسالة مختصرة بس."""
    error_type = type(exc).__name__
    summary = str(exc)[:MAX_ERROR_SUMMARY_LENGTH]
    return error_type, summary


def record_tool_failure(tool_name: str, exc: Exception, chat_id=None, latency_ms=None) -> None:
    """
    يسجّل فشل حقيقي (execution_source="real_use") لأداة معيّنة. best-effort
    بالكامل -- مفيش استثناء بيتسرب برّه الدالة دي أبدًا، بصرف النظر عن سبب
    الفشل جوه التسجيل نفسه.
    """
    try:
        error_type, summary = sanitize_error(exc)

        event_id = event_store.record_event(
            entity_type="tool_health",
            entity_id=tool_name,
            attribute="real_use_failure",
            new_value={"error_type": error_type},
            source="system",
            actor="claude_service._execute_tool",
        )

        from services.firebase_service import firestore_db
        if firestore_db is not None:
            firestore_db.collection(TOOL_FAILURES_LOG_COLLECTION).document().set({
                "tool_name": tool_name,
                "failed_at": now_cairo().isoformat(),
                "execution_source": "real_use",
                "error_type": error_type,
                "sanitized_error_summary": summary,
                "latency_ms": latency_ms,
                "chat_id_present": chat_id is not None,
                "evidence_event_id": event_id,
            })
    except Exception as observer_err:
        logger.error(
            f"❌ فشل تسجيل tool_failures_log لـ {tool_name} (مش حرج -- الخطأ الأصلي كمّل زي ما هو): {observer_err}"
        )
