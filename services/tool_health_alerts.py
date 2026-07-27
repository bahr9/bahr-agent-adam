# -*- coding: utf-8 -*-
"""
🔔 Alerting Through Existing Infrastructure -- Runtime Capabilities & Tool Health V1
=====================================================
صفر منصة إشعار جديدة -- التنبيه بيتبعت عبر `send_message_fn` اللي بينادَى
عليها بـ `bot.send_message` الحقيقي (main.py)، نفس الآلية المستخدمة في
check_loans_job/self_state_active_check_job بالظبط. الفصل بين المنطق هنا
والإرسال الفعلي مقصود: (أ) يسهّل الاختبار من غير Telegram حقيقي، (ب) يمنع
أي احتمال "حلقة تنبيه" -- الوحدة دي مالهاش أي وصول مباشر لـ bot، ومفيش أي
جزء منها بيراقب فعل الإرسال نفسه كأنه "أداة" (bot.send_message مش مسجّلة
في الـ Registry أصلًا).

Dedup + Cooldown + Recovery -- حالة أقل تخزين ممكنة (نفس فلسفة decision_engine
في Stage 5: "آخر مستوى اتبلّغ بيه" بس، مش تاريخ كامل):
  - سجل واحد لكل tool_name في tool_health_alert_state -- last_status,
    last_cause, last_alerted_at.
  - تنبيه بيتبعت *بس* لو: (أ) الأداة دخلت DEGRADED لأول مرة، أو (ب) لسه
    DEGRADED لكن السبب الغالب (dominant error_type) اتغيّر، أو (ج) أداة
    كانت DEGRADED واتعافت. صفر تنبيه لمجرد فحص heartbeat فشل مرة واحدة
    (ده الفرق بين "فشل مسجّل" و"تنبيه اتبعت" -- مش كل فشل يستاهل إزعاج أحمد).
  - Cooldown (ALERT_COOLDOWN_MINUTES) -- شبكة أمان إضافية حتى لو منطق
    الـtransition سمح بتنبيه، مايتبعتش تنبيهين لنفس الأداة في مدة قصيرة.
"""

from datetime import datetime

from config import TOOL_HEALTH_ALERT_STATE_COLLECTION
from utils.time_utils import now_cairo
from utils.logger import logger

ALERT_COOLDOWN_MINUTES = 60


def _get_alert_state(tool_name: str) -> dict:
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return {}
    try:
        doc = firestore_db.collection(TOOL_HEALTH_ALERT_STATE_COLLECTION).document(tool_name).get()
        return doc.to_dict() if doc.exists else {}
    except Exception:
        return {}


def _set_alert_state(tool_name: str, data: dict) -> None:
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return
    try:
        firestore_db.collection(TOOL_HEALTH_ALERT_STATE_COLLECTION).document(tool_name).set(data, merge=True)
    except Exception as e:
        logger.error(f"❌ فشل تسجيل tool_health_alert_state لـ {tool_name} (مش حرج): {e}")


def _dominant_cause(detail: dict):
    by_cause = (detail or {}).get("by_cause") or {}
    if not by_cause:
        return None
    return max(by_cause.items(), key=lambda kv: kv[1])[0]


def _render_alert_text(tool_name: str, kind: str, evaluation: dict) -> str:
    detail = evaluation.get("detail", {})
    if kind == "entered_degraded":
        return f"⚠️ تنبيه صحة أداة: '{tool_name}' بقت DEGRADED -- {detail}"
    if kind == "cause_changed":
        return f"⚠️ تنبيه صحة أداة: '{tool_name}' لسه DEGRADED لكن السبب الغالب اتغيّر -- {detail}"
    if kind == "recovered":
        return f"✅ تعافي أداة: '{tool_name}' رجعت {evaluation['status']} بعد ما كانت DEGRADED"
    return f"تحديث صحة أداة: '{tool_name}' -- {evaluation['status']}"


def maybe_alert(evaluations: dict, send_message_fn) -> list:
    """
    evaluations: ناتج tool_health_engine.evaluate_all_tools() بالظبط.
    send_message_fn: callable(text: str) -- بيتنادى بس لما تنبيه حقيقي لازم
    يتبعت (عادةً lambda text: bot.send_message(chat_id, text)).
    بترجع قايمة التنبيهات اللي اتبعتت فعليًا -- مفيدة للوج/الاختبار.
    """
    sent = []
    now = now_cairo()

    for tool_name, ev in evaluations.items():
        state = _get_alert_state(tool_name)
        prev_status = state.get("last_status")
        prev_cause = state.get("last_cause")
        last_alerted_at = state.get("last_alerted_at")

        current_status = ev["status"]
        current_cause = _dominant_cause(ev.get("detail"))

        should_alert = False
        alert_kind = None

        if current_status == "DEGRADED":
            if prev_status != "DEGRADED":
                should_alert, alert_kind = True, "entered_degraded"
            elif current_cause and current_cause != prev_cause:
                should_alert, alert_kind = True, "cause_changed"
        elif prev_status == "DEGRADED" and current_status in ("HEALTHY", "WATCH", "NOT_MONITORED", "UNKNOWN"):
            should_alert, alert_kind = True, "recovered"

        if should_alert and last_alerted_at:
            try:
                elapsed_minutes = (now - datetime.fromisoformat(last_alerted_at)).total_seconds() / 60.0
                if elapsed_minutes < ALERT_COOLDOWN_MINUTES:
                    should_alert = False
            except Exception:
                pass

        if should_alert:
            text = _render_alert_text(tool_name, alert_kind, ev)
            try:
                send_message_fn(text)
                sent.append({"tool_name": tool_name, "kind": alert_kind, "text": text})
                _set_alert_state(tool_name, {
                    "last_status": current_status,
                    "last_cause": current_cause,
                    "last_alerted_at": now.isoformat(),
                    "last_alert_kind": alert_kind,
                })
            except Exception as e:
                logger.error(f"❌ فشل إرسال تنبيه صحة الأداة {tool_name} (مش حرج): {e}")
                _set_alert_state(tool_name, {"last_status": current_status, "last_cause": current_cause})
        # لو should_alert=False (سواء مفيش انتقال أصلًا أو الـcooldown منع الإرسال) --
        # **عمدًا مفيش أي كتابة هنا**. last_status/last_cause المخزّنين لازم يفضلوا
        # يمثّلوا "آخر حالة/سبب اتبعت عنه تنبيه فعليًا" بس -- لو حدّثناهم هنا كمان،
        # أي تغيّر اتقمع بالـcooldown هيتنسى بصمت وهيفوت لما الـcooldown ينتهي (باگ
        # حقيقي اتكشف واتصلح أثناء test_alerting_dedup_cooldown_recovery).

    return sent
