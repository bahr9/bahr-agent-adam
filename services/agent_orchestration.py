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

# الأكشنز اللي فعليًا عندها تنفيذ آلي حقيقي شغال دلوقتي، لكل target.
# ملحوظة: مش allowlist صارم بيرفض حاجة تانية -- action حر لسه مسموح
# (تاسك عام يقعد pending لحد ما حد يراجعه يدويًا). ده بس مرجع نعرف بيه
# نصحح للموديل لو هو قاصد أوتوميشن حقيقي واستخدم string غلط.
AUTOMATED_ACTIONS_BY_TARGET = {
    "مداد": {"generate_marketing_post_from_eye_expert"},
    "عين_الخبير": {"retry_failed_eye_expert_reply", "retry_failed_eye_expert_reply_test"},
    "Hope": set(),
}

# دورة الـ poll الفعلية لكل نظام -- مداد بايثون بوت بيعمل poll كل دقيقتين،
# عين الخبير بقى Make.com scenario بيعمل poll كل 20 دقيقة.
POLL_INTERVAL_DESCRIPTION_BY_TARGET = {
    "مداد": "كل دقيقتين",
    "عين_الخبير": "كل 20 دقيقة",
}


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

        known_actions = AUTOMATED_ACTIONS_BY_TARGET.get(target, set())
        if action in known_actions:
            poll_desc = POLL_INTERVAL_DESCRIPTION_BY_TARGET.get(target, "بشكل دوري")
            message = (
                f"اتسجل التاسك لـ {target} (action='{action}') وهيتنفذ آليًا فعلاً -- "
                f"{target} بيعمل poll {poll_desc}، فمتوقع ينفّذ ويتحدّث حالته قريب."
            )
        elif known_actions:
            message = (
                f"اتسجل التاسك لـ {target} بس بـ action='{action}' اللي مش من أكشنز الأوتوميشن "
                f"المعروفة لـ {target} ({', '.join(sorted(known_actions))}). هيفضل pending لحد ما "
                f"حد يراجعه يدويًا. لو قصدك تشغيل التنفيذ الآلي الحقيقي، ابعت تاني بالظبط بـ "
                f"action='{sorted(known_actions)[0]}'."
            )
        else:
            message = (
                f"اتسجل التاسك لـ {target} وهو معلّق (pending) -- مفيش تنفيذ آلي مبني لـ {target} لسه، "
                f"فهيفضل قاعد لحد ما حد يراجعه يدويًا."
            )

        return {
            "ok": True,
            "task_id": doc_ref.id,
            "message": message,
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


def verify_task_completion(task: dict) -> dict:
    """
    تحقق حقيقي من نتيجة تاسك status='done' -- بيقرا الدليل الفعلي من نفس
    مصدر البيانات المذكور في result.verification، مش بس يصدّق result.summary.
    لسه بيدعم نوع واحد بس (firestore_document) لأنه ده اللي مبني فعليًا
    (اختبار echo_test_marker). أي نوع تاني بيترجع verified=False صراحة.
    """
    result = task.get("result") or {}
    verification = result.get("verification")
    if not verification:
        return {"verified": False, "reason": "مفيش دليل تحقق مرفق مع التاسك -- الادّعاء مش متأكد"}

    v_type = verification.get("type")

    if v_type == "firestore_document":
        from services.firebase_service import firestore_db
        collection = verification.get("collection")
        expected_marker = verification.get("expected_marker")
        field = verification.get("field", "caption")
        if firestore_db is None:
            return {"verified": False, "reason": "Firestore مش متصل -- مينفعش نتحقق"}
        if not collection or not expected_marker:
            return {"verified": False, "reason": "بيانات التحقق ناقصة (collection/expected_marker)"}
        try:
            docs = firestore_db.collection(collection).where(field, "==", expected_marker).limit(1).stream()
            if any(True for _ in docs):
                return {"verified": True, "reason": f"اتأكد فعليًا -- المستند موجود في {collection}"}
            return {"verified": False, "reason": f"مفيش مستند مطابق في {collection} -- الادّعاء مش مؤكد"}
        except Exception as e:
            return {"verified": False, "reason": f"خطأ أثناء التحقق: {e}"}

    return {"verified": False, "reason": f"نوع تحقق غير مدعوم عند آدم لسه: {v_type}"}


def get_unreported_completed_tasks() -> list:
    """التاسكات اللي خلصت (done/failed) ولسه محدش بلّغ أحمد بيها."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(AGENT_TASKS_COLLECTION).limit(500).stream()
        tasks = [doc.to_dict() for doc in docs]
        return [
            t for t in tasks
            if t.get("status") in ("done", "failed") and not t.get("reported_to_ahmed")
        ]
    except Exception as e:
        logger.error(f"❌ خطأ في جلب التاسكات المكتملة: {e}")
        return []


def mark_task_reported(task_id: str) -> None:
    """تعليم تاسك كمُبلّغ لأحمد -- منع تكرار التبليغ عنه تاني."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return
    try:
        firestore_db.collection(AGENT_TASKS_COLLECTION).document(task_id).set(
            {"reported_to_ahmed": True}, merge=True
        )
    except Exception as e:
        logger.error(f"❌ خطأ في تعليم التاسك كمُبلّغ {task_id}: {e}")


def update_agent_task_status(task_id: str, status: str, result: dict = None) -> bool:
    """
    تحديث حالة تاسك من طرف تنفيذ خارجي (زي بولينج Make بتاع عين الخبير عبر
    /agent-tasks/<id>/status) -- بيتاخد بس لما status يكون 'done' أو 'failed'
    فعليًا؛ حالة 'skip' (الأكشن مش معروف) متبعتش هنا خالص، التاسك يفضل pending.
    """
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return False
    try:
        update_data = {
            "status": status,
            "updated_at": now_cairo().isoformat(),
        }
        if result is not None:
            update_data["result"] = result
        firestore_db.collection(AGENT_TASKS_COLLECTION).document(task_id).set(
            update_data, merge=True
        )
        logger.info(f"🕸️ Agent task {task_id} -> {status} (عبر endpoint خارجي)")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث حالة التاسك {task_id}: {e}")
        return False


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


# ============================================================
# 🐘 بلوك أولوية Supabase (نقل الطابور -- 2026-08-06)
# ============================================================
# نفس نمط firebase_service بالظبط: التعريفات الأصلية فوق محفوظة كـ fallback
# بأسماء _fs_*، والأسماء العامة بتحاول Supabase الأول. الكتابة مزدوجة
# (Supabase + mirror للمسار القديم) عشان عين الخبير (Make.com بيلمس
# Firestore عبر endpoints آدم) والرجوع يفضلوا شغالين طول الانتقال.

from services import supabase_store as _sbq

_fs_dispatch_agent_task = dispatch_agent_task
_fs_get_agent_task_status = get_agent_task_status
_fs_list_agent_tasks = list_agent_tasks
_fs_get_unreported_completed_tasks = get_unreported_completed_tasks
_fs_mark_task_reported = mark_task_reported
_fs_update_agent_task_status = update_agent_task_status
_fs_list_stale_agent_tasks = list_stale_agent_tasks


def dispatch_agent_task(target, action, payload=None):
    result = _fs_dispatch_agent_task(target, action, payload)
    task_id = (result or {}).get("task_id")
    if task_id:
        if not _sbq.q_dispatch(task_id, target, action, payload):
            from utils.logger import logger as _lg
            _lg.error(f"❌ التاسك {task_id} اتكتب في Firestore بس -- Supabase فشل! "
                      f"مداد (لو بيقرا من Supabase) مش هيشوفه.")
    return result


def get_agent_task_status(task_id):
    sb = _sbq.q_get_task(task_id)
    if sb is not None and not sb.get("__missing__"):
        return sb
    return _fs_get_agent_task_status(task_id)


def list_agent_tasks(target=None, status=None, limit=50):
    sb = _sbq.q_list(target, status, limit)
    if sb is not None:
        return sb
    return _fs_list_agent_tasks(target, status, limit)


def get_unreported_completed_tasks():
    sb = _sbq.q_unreported_done()
    if sb is not None:
        return sb
    return _fs_get_unreported_completed_tasks()


def mark_task_reported(task_id):
    _sbq.q_mark_reported(task_id)
    try:
        _fs_mark_task_reported(task_id)
    except Exception:
        pass


def update_agent_task_status(task_id, status, result=None):
    sb_ok = _sbq.q_update_status(task_id, status, result)
    try:
        fs_ok = _fs_update_agent_task_status(task_id, status, result)
    except Exception:
        fs_ok = False
    return sb_ok or fs_ok


def list_stale_agent_tasks(days=3):
    sb = _sbq.q_stale(days)
    if sb is not None:
        return sb
    return _fs_list_stale_agent_tasks(days)
