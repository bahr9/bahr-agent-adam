# -*- coding: utf-8 -*-
"""
🏗️ Project Status Alerts -- Bahr OS Projects (external, read-only)
=====================================================
مشاريع Bahr OS (get_bahr_projects) بتتقرأ من مجموعة Firestore "projects" --
نظام خارجي (Bahr OS) بيدير الكتابة فيها، آدم بيقراها بس (read-only). الحالات
الممكنة: active / delayed / suspended / completed (services/claude_service.py
tool schema).

نفس فلسفة tool_health_alerts.py بالظبط -- Dedup + Cooldown بأقل حالة تخزين
ممكنة (سجل واحد لكل project_id: last_status, last_alerted_at). تنبيه بيتبعت
*بس* لما مشروع يدخل حالة مقلقة (delayed/suspended) لأول مرة، أو يتعافى منها --
صفر تنبيه لمجرد إن المشروع لسه في نفس الحالة من فحص لفحص.
"""

from datetime import datetime

from config import PROJECT_STATUS_ALERT_STATE_COLLECTION
from utils.time_utils import now_cairo
from utils.logger import logger

CONCERNING_STATUSES = {"delayed", "suspended"}
ALERT_COOLDOWN_MINUTES = 60


def _get_alert_state(project_id: str) -> dict:
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return {}
    try:
        doc = firestore_db.collection(PROJECT_STATUS_ALERT_STATE_COLLECTION).document(project_id).get()
        return doc.to_dict() if doc.exists else {}
    except Exception:
        return {}


def _set_alert_state(project_id: str, data: dict) -> None:
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return
    try:
        firestore_db.collection(PROJECT_STATUS_ALERT_STATE_COLLECTION).document(project_id).set(data, merge=True)
    except Exception as e:
        logger.error(f"❌ فشل تسجيل project_status_alert_state لـ {project_id} (مش حرج): {e}")


def _render_alert_text(project: dict, kind: str) -> str:
    client = project.get("client") or project.get("id")
    status = project.get("status", "")
    if kind == "entered_concerning":
        return f"⚠️ مشروع '{client}' بقت حالته '{status}' -- يستاهل متابعة."
    if kind == "recovered":
        return f"✅ مشروع '{client}' رجع لحالة عادية ({status})."
    return f"تحديث مشروع '{client}': {status}"


def check_project_status_alerts(send_message_fn) -> list:
    """
    بتجيب مشاريع Bahr OS الحالية، تقارنها بآخر حالة معروفة، وتبعت تنبيه بس
    عند انتقال حقيقي (دخول/خروج من delayed/suspended). send_message_fn:
    callable(text: str) -- نفس نمط tool_health_alerts.maybe_alert.
    بترجع قايمة التنبيهات اللي اتبعتت فعليًا -- مفيدة للوج/الاختبار.
    """
    from services.firebase_service import get_bahr_projects

    sent = []
    now = now_cairo()

    for project in get_bahr_projects():
        project_id = project.get("id")
        if not project_id:
            continue

        current_status = (project.get("status") or "").strip().lower()
        state = _get_alert_state(project_id)
        prev_status = state.get("last_status")
        last_alerted_at = state.get("last_alerted_at")

        should_alert = False
        alert_kind = None

        if current_status in CONCERNING_STATUSES:
            if prev_status not in CONCERNING_STATUSES:
                should_alert, alert_kind = True, "entered_concerning"
        elif prev_status in CONCERNING_STATUSES:
            should_alert, alert_kind = True, "recovered"

        if should_alert and last_alerted_at:
            try:
                elapsed_minutes = (now - datetime.fromisoformat(last_alerted_at)).total_seconds() / 60.0
                if elapsed_minutes < ALERT_COOLDOWN_MINUTES:
                    should_alert = False
            except Exception:
                pass

        if should_alert:
            text = _render_alert_text(project, alert_kind)
            try:
                send_message_fn(text)
                sent.append({"project_id": project_id, "kind": alert_kind, "text": text})
                _set_alert_state(project_id, {
                    "last_status": current_status,
                    "last_alerted_at": now.isoformat(),
                    "last_alert_kind": alert_kind,
                })
            except Exception as e:
                logger.error(f"❌ فشل إرسال تنبيه حالة المشروع {project_id}: {e}")
                # ممنوع نكتب الحالة هنا (أوديت 2026-08-05). الكتابة كانت
                # بتخلي الدورة الجاية تشوف prev == current يعني "مفيش انتقال"،
                # فالتنبيه كان بيضيع **للأبد** بسبب فشل شبكة لحظي واحد -- وده
                # حصل فعلاً في لوج 2026-08-04. من غير كتابة، الانتقال يفضل
                # مكتشَف والتنبيه يتعاد الدورة الجاية.
        # لو should_alert=False -- عمدًا مفيش أي كتابة هنا، نفس سبب
        # tool_health_alerts.py: last_status لازم يفضل يمثّل "آخر حالة اتبعت
        # عنها تنبيه فعليًا" بس، عشان الـcooldown ميبلعش تغيّرات حقيقية.

    return sent
