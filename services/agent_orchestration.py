# -*- coding: utf-8 -*-
"""
🕸️ Agent Orchestration -- المرحلة 1 (Task Schema + Firestore Queue)
=====================================================
آدم بيبعت "تاسكات" لباقي الأنظمة (Hope / مداد / عين الخبير) عن طريق طابور
واحد في Firestore، مش نداء مباشر -- لأن الأنظمة دي لسه مالهاش endpoint
يستقبل منه (المرحلة 2، مش شغل آدم). التاسك بيتسجل بـ status="pending"
ويفضل قاعد لحد ما نظام تاني (أو آدم نفسه لاحقًا) يحدّث حالته.

Schema (نفس البريف المعتمد):
    {
        "task_id": "...",        -- نفس الـ Firestore document id
        "source": "ADAM",
        "target": "Hope" | "مداد" | "عين_الخبير",
        "action": "...",
        "payload": {...},
        "status": "pending" | "in_progress" | "done" | "failed",
        "created_at": ISO timestamp,
        "updated_at": ISO timestamp,
    }

ملحوظة مهمة: دلوقتي الطابور ده "يبعت وينسى" فعليًا -- مفيش نظام بيستهلك منه
لسه. الأداة هنا صادقة عن ده (بترجع رسالة توضّح إن التاسك اتسجل بس لسه معلّق).
"""

from datetime import timedelta

from utils.logger import logger
from utils.time_utils import now_cairo
from config import AGENT_TASKS_COLLECTION

VALID_TARGETS = ["Hope", "مداد", "عين_الخبير"]
PENDING_STATUSES = ("pending", "in_progress")


def dispatch_agent_task(target: str, action: str, payload: dict = None) -> dict:
    """
    تسجيل تاسك جديد في الطابور. مش تنفيذ فعلي -- التاسك بيفضل pending لحد ما
    نظام تاني يستهلكه (أو حد يحدّث حالته يدويًا لحد ما تتبني المرحلة 2).
    """
    if target not in VALID_TARGETS:
        return {
            "ok": False,
            "task_id": None,
            "message": f"الهدف '{target}' مش من الأنظمة المعروفة ({', '.join(VALID_TARGETS)})",
        }

    from services.firebase_service import firestore_db
    if firestore_db is None:
        return {"ok": False, "task_id": None, "message": "Firestore مش متصل"}

    try:
        now = now_cairo().isoformat()
        doc_ref = firestore_db.collection(AGENT_TASKS_COLLECTION).document()
        doc_ref.set({
            "task_id": doc_ref.id,
            "source": "ADAM",
            "target": target,
            "action": action,
            "payload": payload or {},
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        })
        logger.info(f"🕸️ Agent task dispatched: {target} <- {action} (id={doc_ref.id})")
        return {
            "ok": True,
            "task_id": doc_ref.id,
            "message": f"اتسجل التاسك لـ {target} وهو معلّق (pending) -- مفيش نظام مستقبِل بيستهلكه لسه.",
        }
    except Exception as e:
        logger.error(f"❌ خطأ في تسجيل agent task: {e}")
        return {"ok": False, "task_id": None, "message": "حصلت مشكلة أثناء التسجيل"}


def get_agent_task_status(task_id: str) -> dict:
    """جلب حالة تاسك واحد بالـ ID بتاعه."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return {}
    try:
        doc = firestore_db.collection(AGENT_TASKS_COLLECTION).document(task_id).get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        logger.error(f"❌ خطأ في جلب حالة التاسك {task_id}: {e}")
        return {}


def list_agent_tasks(target: str = None, status: str = None, limit: int = 50) -> list:
    """جلب التاسكات، مع فلترة اختيارية بالهدف و/أو الحالة."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(AGENT_TASKS_COLLECTION).limit(500).stream()
        tasks = [doc.to_dict() for doc in docs]
        if target:
            tasks = [t for t in tasks if t.get("target") == target]
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return tasks[:limit]
    except Exception as e:
        logger.error(f"❌ خطأ في جلب التاسكات: {e}")
        return []


def list_stale_agent_tasks(days: int = 3) -> list:
    """
    التاسكات اللي لسه pending/in_progress وعدّى عليها أكتر من `days` يوم من
    غير ما تتحدّث حالتها -- مستخدمة في المبادرة الاستباقية (تنبيه آدم لأحمد
    إن فيه تاسك عالق).
    """
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []

    cutoff_iso = (now_cairo() - timedelta(days=days)).isoformat()

    try:
        docs = firestore_db.collection(AGENT_TASKS_COLLECTION).limit(500).stream()
        stale = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("status") not in PENDING_STATUSES:
                continue
            if data.get("created_at", "") <= cutoff_iso:
                stale.append(data)
        stale.sort(key=lambda t: t.get("created_at", ""))
        return stale
    except Exception as e:
        logger.error(f"❌ خطأ في جلب التاسكات العالقة: {e}")
        return []
