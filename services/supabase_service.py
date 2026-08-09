# -*- coding: utf-8 -*-
"""
🐘 خدمة Supabase (Postgres)
- Pilot: بديل Firestore للتذكيرات المتكررة بس (recurring_reminders)
- عمليات CRUD خام بحتة -- صفر منطق dual-write أو fallback هنا،
  ده كله في services/recurring_reminders_service.py
"""

from utils.logger import logger, _is_test_process
from config import SUPABASE_URL, SUPABASE_KEY, RECURRING_REMINDERS_TABLE

supabase_client = None


def init_supabase():
    """تهيئة الاتصال بـ Supabase -- soft-optional، مبيرميش لو المفاتيح مش موجودة.

    ممنوع من تشغيلات الاختبار (2026-08-09). الحادثة:
    `test_endpoint_security.py` بيعمل `from main import flask_app`، واستيراد
    `main` بينفّذ `init_supabase()` على مستوى الموديول. مع المشغّل القديم
    (عملية لكل ملف) ده كان بيوصّل ملف واحد بالإنتاج ويخلص، وتحت pytest --
    عملية واحدة -- العميل الحقيقي كان بيفضل مركّب لكل الـ44 ملف اللي بعده،
    فالسويت كانت **بتقرا من Supabase الإنتاج** وهي فاكرة نفسها معزولة.
    اتكشف بحارس تلوث، مش بفشل صريح.

    المنع هنا مش في ملفات الاختبار عن قصد: نقطة الاتصال واحدة، وأي مسار
    جديد بيستورد `main` هيتحمي تلقائيًا من غير ما حد يفتكر.
    """
    global supabase_client

    if _is_test_process():
        logger.warning(
            "🚫 اتصال Supabase اترفض -- العملية دي تشغيلة اختبار. "
            "لو شايف السطر ده في الإنتاج يبقى كاشف البيئة غلط، وآدم هيشتغل "
            "من غير قاعدة بيانات."
        )
        return False

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("⚠️ SUPABASE_URL/SUPABASE_KEY مش موجودين -- التذكيرات المتكررة هتشتغل بـ Firestore بس")
        return False

    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ اتصلت بـ Supabase")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في الاتصال بـ Supabase: {e}")
        return False


def insert_reminder(text, interval_type, interval_value, chat_id, scheduled_hour=None, scheduled_minute=None):
    """إضافة تذكير متكرر جديد -- بيرجع الصف الكامل (فيه الـ id) أو None"""
    if supabase_client is None:
        return None
    try:
        resp = supabase_client.table(RECURRING_REMINDERS_TABLE).insert({
            "text": text,
            "interval_type": interval_type,
            "interval_value": interval_value,
            "chat_id": chat_id,
            "scheduled_hour": scheduled_hour,
            "scheduled_minute": scheduled_minute or 0,
            "active": True,
        }).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"❌ [Supabase] خطأ في حفظ التذكير المتكرر: {e}")
        return None


def select_active_reminders():
    """
    جلب كل التذكيرات المتكررة النشطة.
    بيرجع None لو القراءة فشلت (عشان الطبقة اللي فوق تفرّق بين "فشل" و"فعلاً صفر تذكيرات")،
    وبيرجع [] لو نجحت القراءة ومفيش تذكيرات نشطة.
    """
    if supabase_client is None:
        return None
    try:
        resp = supabase_client.table(RECURRING_REMINDERS_TABLE).select("*").eq("active", True).execute()
        return resp.data or []
    except Exception as e:
        logger.error(f"❌ [Supabase] خطأ في جلب التذكيرات المتكررة: {e}")
        return None


def update_last_sent(reminder_id, now_ms):
    """تحديث آخر وقت إرسال لصف معيّن، بالـ Supabase id بتاعه.

    بيشتغل مع نوعين العمود (تحضير هجرة 2026-08-05): بيجرّب يكتب نص ISO
    (المناسب لـ timestamptz) الأول، ولو العمود لسه bigint الكتابة بتترفض
    فبيرجع يكتب epoch بالميلي. كده تحويل العمود في قاعدة البيانات ينفع
    يحصل قبل نشر الكود أو بعده -- من غير أي نافذة مكسورة في النص.
    """
    if supabase_client is None:
        return False

    from datetime import datetime, timezone
    iso_value = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).isoformat()

    for value, label in ((iso_value, "timestamptz"), (now_ms, "epoch_ms")):
        try:
            supabase_client.table(RECURRING_REMINDERS_TABLE).update(
                {"last_sent": value}
            ).eq("id", reminder_id).execute()
            return True
        except Exception as e:
            logger.warning(
                f"⚠️ [Supabase] كتابة last_sent كـ {label} فشلت ({reminder_id}): {str(e)[:90]}"
            )

    logger.error(f"❌ [Supabase] فشل تحديث آخر وقت إرسال بالشكلين ({reminder_id})")
    return False


def update_firestore_id(reminder_id, firestore_id):
    """ربط صف Supabase بمستند Firestore المقابل (best-effort، بعد نجاح الكتابة في الاتنين)"""
    if supabase_client is None:
        return False
    try:
        supabase_client.table(RECURRING_REMINDERS_TABLE).update({"firestore_id": firestore_id}).eq("id", reminder_id).execute()
        return True
    except Exception as e:
        logger.error(f"❌ [Supabase] فشل ربط firestore_id بصف {reminder_id}: {e}")
        return False


def get_by_id(reminder_id):
    """جلب صف واحد بالـ id -- بيرجع الصف أو None لو مش موجود/فشلت القراءة"""
    if supabase_client is None:
        return None
    try:
        resp = supabase_client.table(RECURRING_REMINDERS_TABLE).select("*").eq("id", reminder_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"❌ [Supabase] خطأ في جلب الصف {reminder_id}: {e}")
        return None


def delete_by_id(reminder_id):
    """حذف صف بالـ id"""
    if supabase_client is None:
        return False
    try:
        supabase_client.table(RECURRING_REMINDERS_TABLE).delete().eq("id", reminder_id).execute()
        return True
    except Exception as e:
        logger.error(f"❌ [Supabase] خطأ في حذف الصف {reminder_id}: {e}")
        return False
