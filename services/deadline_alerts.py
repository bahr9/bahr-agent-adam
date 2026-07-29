# -*- coding: utf-8 -*-
"""
⏳ Urgent Deadline Alerts -- memory_notes مع [Deadline: ...]
=====================================================
get_upcoming_deadlines() (services/firebase_service.py) بتحسب "urgent" لأي
ملاحظة عليها deadline خلال 3 أيام. النظام الحالي بيعرضها بس مرة واحدة يوميًا
جوه Morning Brief -- ده كافي لمواعيد بعيدة، لكن مش سريع كفاية لموعد فعلًا
قريب (3 أيام أو أقل). الموديول ده بيضيف مسار تنبيه منفصل وأسرع (كل ساعة)
للحالات العاجلة بس، من غير ما يكرر أي حاجة اتبلّغ عنها قبل كده.

Dedup: علم `urgent_alert_sent` بيتسجل على مستند الملاحظة نفسها في
memory_notes (مش مجموعة منفصلة) -- أبسط حاجة ممكنة، ومربوط طبيعيًا بالملاحظة
نفسها.
"""

from utils.logger import logger
from services.firebase_service import MEMORY_NOTES_COLLECTION


def _mark_alerted(note_id: str) -> None:
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return
    try:
        firestore_db.collection(MEMORY_NOTES_COLLECTION).document(note_id).update(
            {"urgent_alert_sent": True}
        )
    except Exception as e:
        logger.error(f"❌ فشل تسجيل urgent_alert_sent للملاحظة {note_id} (مش حرج): {e}")


def check_urgent_deadline_alerts(user_id: str, send_message_fn) -> list:
    """
    بتجيب الـ deadlines العاجلة (خلال 3 أيام) اللي لسه ما اتبلّغ عنهاش،
    تبعت تنبيه واحد لكل واحدة، وتعلّمها كـ 'اتبعت'. send_message_fn:
    callable(text: str). بترجع قايمة اللي اتبعت فعليًا -- مفيدة للوج/الاختبار.
    """
    from services.firebase_service import get_upcoming_deadlines, firestore_db

    if firestore_db is None:
        return []

    sent = []
    data = get_upcoming_deadlines(user_id, days_ahead=3)

    for deadline in data.get("deadlines", []):
        if not deadline.get("urgent"):
            continue

        note_id = deadline["id"]
        try:
            doc = firestore_db.collection(MEMORY_NOTES_COLLECTION).document(note_id).get()
            already_sent = bool(doc.to_dict().get("urgent_alert_sent")) if doc.exists else True
        except Exception:
            already_sent = True  # لو فشل التأكد، أأمن حاجة إننا ما نكررش تنبيه

        if already_sent:
            continue

        text = (
            f"⏳ موعد قريب: {deadline['text']} -- بعد {deadline['days_remaining']} يوم "
            f"({deadline['deadline']})"
        )
        try:
            send_message_fn(text)
            sent.append({"note_id": note_id, "text": text})
            _mark_alerted(note_id)
        except Exception as e:
            logger.error(f"❌ فشل إرسال تنبيه الموعد العاجل {note_id} (مش حرج): {e}")

    return sent
