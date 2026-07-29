# -*- coding: utf-8 -*-
"""
📋 خدمة المهام والأفكار الشخصية (Personal Tasks & Ideas)
- مهام سريعة: /save /tasks /done /clear
- أفكار عابرة: /ideas
- التخزين في Firestore -- نفس نمط باقي التطبيق (مفيش نسخة محلية، البيانات
  دي مش critical زي التذكيرات اللي محتاجة local backup).

ملحوظة معمارية: مختلفة عمدًا عن office_tasks (services/firebase_service.py)
-- office_tasks خاصة بمهام المكتب/المشاريع، ودي مهام شخصية سريعة بأمر /save.
"""

import time

from utils.logger import logger
from config import PERSONAL_TASKS_COLLECTION, IDEAS_COLLECTION

# ============================================================
# 📋 المهام
# ============================================================

def add_task(text: str) -> bool:
    """حفظ مهمة جديدة"""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(PERSONAL_TASKS_COLLECTION).document().set({
            "نص": text,
            "تم": False,
            "created_at": int(time.time() * 1000),
        })
        logger.info(f"📋 Task saved: {text[:50]}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ المهمة: {e}")
        return False


def get_all_tasks() -> list:
    """جلب كل المهام مرتبة من الأقدم للأحدث (نفس ترتيب /save) -- الترتيب
    ده مهم لأن /done بيرجع بالرقم المعروض في /tasks."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(PERSONAL_TASKS_COLLECTION).limit(500).stream()
        rows = [(doc.id, doc.to_dict()) for doc in docs]
        rows.sort(key=lambda item: item[1].get("created_at", 0))
        return [
            {"id": doc_id, "نص": data.get("نص", ""), "تم": data.get("تم", False)}
            for doc_id, data in rows
        ]
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المهام: {e}")
        return []


def mark_task_done(task_num: int):
    """
    تأكيد إنجاز مهمة برقمها (1-based -- نفس الرقم المعروض في /tasks).

    Returns:
        (True, نص المهمة) عند النجاح، (False, رسالة الخطأ) عند الفشل.
    """
    tasks = get_all_tasks()

    if task_num < 1 or task_num > len(tasks):
        return False, f"مفيش مهمة رقم {task_num}"

    task = tasks[task_num - 1]

    from services.firebase_service import firestore_db
    if firestore_db is None:
        return False, "Firestore مش متصل"

    try:
        firestore_db.collection(PERSONAL_TASKS_COLLECTION).document(task["id"]).update({"تم": True})
        return True, task["نص"]
    except Exception as e:
        logger.error(f"❌ خطأ في تأكيد المهمة: {e}")
        return False, "حصلت مشكلة أثناء الحفظ"


def clear_all_tasks() -> bool:
    """مسح كل المهام"""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return False
    try:
        docs = firestore_db.collection(PERSONAL_TASKS_COLLECTION).stream()
        for doc in docs:
            doc.reference.delete()
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في مسح المهام: {e}")
        return False


def get_stale_tasks(days: int = 7) -> list:
    """
    المهام اللي لسه مش متعملة ('تم': False) وعدّى عليها أكتر من `days` يوم
    من وقت إضافتها. مستخدمة في المبادرة الاستباقية -- آدم يفكّر أحمد بالمهام
    اللي اتنسيت، من غير ما ينتظر يُسأل.
    """
    from utils.time_utils import now_cairo
    cutoff_ms = int(now_cairo().timestamp() * 1000) - (days * 24 * 60 * 60 * 1000)

    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []

    stale = []
    try:
        docs = firestore_db.collection(PERSONAL_TASKS_COLLECTION).limit(500).stream()
        for doc in docs:
            data = doc.to_dict()
            if data.get("تم"):
                continue
            created_at = data.get("created_at", 0)
            if created_at and created_at <= cutoff_ms:
                stale.append({
                    "id": doc.id,
                    "نص": data.get("نص", ""),
                    "created_at": created_at,
                })
        stale.sort(key=lambda t: t["created_at"])
        return stale
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المهام القديمة: {e}")
        return []


# ============================================================
# 💡 الأفكار
# ============================================================

def add_idea(text: str) -> bool:
    """حفظ فكرة جديدة"""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(IDEAS_COLLECTION).document().set({
            "نص": text,
            "created_at": int(time.time() * 1000),
        })
        logger.info(f"💡 Idea saved: {text[:50]}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الفكرة: {e}")
        return False


def get_recent_ideas(limit: int = 10) -> list:
    """جلب آخر الأفكار (الأحدث أولًا)"""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(IDEAS_COLLECTION).limit(500).stream()
        rows = [(doc.id, doc.to_dict()) for doc in docs]
        rows.sort(key=lambda item: item[1].get("created_at", 0), reverse=True)
        return [{"id": doc_id, "نص": data.get("نص", "")} for doc_id, data in rows[:limit]]
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الأفكار: {e}")
        return []


def clear_all_ideas() -> bool:
    """مسح كل الأفكار"""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return False
    try:
        docs = firestore_db.collection(IDEAS_COLLECTION).stream()
        for doc in docs:
            doc.reference.delete()
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في مسح الأفكار: {e}")
        return False
