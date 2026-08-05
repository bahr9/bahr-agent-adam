# -*- coding: utf-8 -*-
"""
🔄 Recurring Reminders -- طبقة التنسيق (Pilot: Firestore -> Supabase)
=====================================================
Firestore هو الشبكة الأمان طول فترة التجربة -- بنكتب في الاتنين، وبنقرا من
Supabase الأول وبس لو فشلت القراءة نرجع لـ Firestore. الملف ده هو المكان
الوحيد اللي المفروض main.py وclaude_service.py وcapabilities_registry.py
يستوردوا منه لأي حاجة خاصة بالتذكيرات المتكررة -- مش من firebase_service.py
مباشرة، ومش من supabase_service.py مباشرة.

firebase_service.py نفسه متلمسش هنا خالص -- ده اللي بيضمن إن الشبكة الأمان
فعلاً شبكة أمان حقيقية (كود مجرّب ومعروف، مش كود جديد اتلمس).
"""

import time
from datetime import timedelta

from utils.logger import logger
from services import supabase_service, firebase_service


# نافذة اللحاق للتذكير اليومي بميعاد محدد (أوديت 2026-08-05).
# بتحل مشكلتين مع بعض: (1) لو البوت كان واقف لحظة الميعاد بالظبط، يلحق
# التذكير أول ما يرجع بدل ما يضيع؛ (2) تذكير جديد اتعمل بعد ميعاده بساعات
# مايضربش فورًا لحظة الإنشاء -- يستنى ميعاد بكرة.
DAILY_CATCHUP_MINUTES = 90

INTERVALS_MS = {
    "daily":  24 * 60 * 60 * 1000,
    "weekly":  7 * 24 * 60 * 60 * 1000,
    "hourly":      60 * 60 * 1000,
}


def is_reminder_due(reminder, now_cairo_time, now_ms):
    """هل التذكير المتكرر ده مستحق الإرسال دلوقتي؟ -- دالة صافية، بلا شبكة.

    للتذكير اليومي بميعاد محدد القاعدة هي: "عدّينا ميعاد النهارده وإحنا لسه
    جوه نافذة اللحاق، ولسه متبعتش بعد الميعاد ده".

    القاعدة القديمة كانت بتطلب `now.minute == scheduled_minute` بالظبط،
    والـ job كان بيشتغل كل 15 دقيقة -- فالدقيقة المطلوبة عمرها ما كانت بتيجي
    والتذكيرات اليومية عمرها ما ضربت. القاعدة الجديدة صح مهما كان إيقاع الفحص.
    """
    last_sent = reminder.get("last_sent")
    interval_type = reminder.get("interval_type", "daily")
    scheduled_hour = reminder.get("scheduled_hour")

    if scheduled_hour is not None and interval_type == "daily":
        target = now_cairo_time.replace(
            hour=int(scheduled_hour),
            minute=int(reminder.get("scheduled_minute") or 0),
            second=0,
            microsecond=0,
        )
        since_target = now_cairo_time - target
        if since_target < timedelta(0):
            return False                       # الميعاد لسه ماجاش النهارده
        if since_target > timedelta(minutes=DAILY_CATCHUP_MINUTES):
            return False                       # فات الميعاد بكتير -- استنى بكرة
        return last_sent is None or last_sent < int(target.timestamp() * 1000)

    if interval_type == "custom_minutes":
        interval_ms = int(reminder.get("interval_value") or 1) * 60 * 1000
    else:
        interval_ms = INTERVALS_MS.get(interval_type, INTERVALS_MS["daily"])

    return last_sent is None or (now_ms - last_sent) >= interval_ms


def save_recurring_reminder(text, interval_type, interval_value, chat_id, scheduled_hour=None, scheduled_minute=None):
    """
    حفظ تذكير متكرر جديد -- في Supabase وFirestore الاتنين.
    بيرجع الـ id بتاع Supabase لو نجح، وإلا id بتاع Firestore، وإلا None.
    """
    supabase_row = supabase_service.insert_reminder(
        text, interval_type, interval_value, chat_id, scheduled_hour, scheduled_minute
    )

    firestore_id = firebase_service.save_recurring_reminder(
        text, interval_type, interval_value, chat_id, scheduled_hour, scheduled_minute
    )

    if supabase_row and firestore_id:
        supabase_service.update_firestore_id(supabase_row["id"], firestore_id)

    if supabase_row:
        return supabase_row["id"]
    return firestore_id


def get_active_recurring_reminders():
    """
    جلب كل التذكيرات المتكررة النشطة.
    بتحاول Supabase الأول؛ لو فشلت، بترجع لـ Firestore (fallback).
    كل عنصر راجع فيه "_source" ("supabase" أو "firestore_fallback") و"firestore_id"
    عشان update/delete بعد كده يعرفوا يحدّثوا/يمسحوا من المكان الصح.
    """
    rows = supabase_service.select_active_reminders()

    if rows is not None:
        logger.info(f"✅ [Supabase] قرأت {len(rows)} تذكير متكرر نشط")
        for row in rows:
            row["_source"] = "supabase"
        return rows

    logger.warning("⚠️ فشلت قراءة Supabase للتذكيرات المتكررة، هرجع لـ Firestore")
    docs = firebase_service.get_active_recurring_reminders()
    for doc in docs:
        doc["_source"] = "firestore_fallback"
        doc["firestore_id"] = doc["id"]
    return docs


def update_recurring_reminder_last_sent(reminder):
    """
    تحديث آخر وقت إرسال. بياخد الـ reminder dict الكامل (مش بس الـ id) عشان
    يعرف يحدّث المصدر الصح (Supabase أو Firestore) ومصدر الـ mirror لو موجود.
    """
    now_ms = int(time.time() * 1000)

    if reminder.get("_source") == "supabase":
        ok = supabase_service.update_last_sent(reminder["id"], now_ms)
        firestore_id = reminder.get("firestore_id")
        if firestore_id:
            mirror_ok = firebase_service.update_recurring_reminder_last_sent(firestore_id)
            if not mirror_ok:
                logger.warning(f"⚠️ نجح تحديث Supabase لكن فشل الـ mirror في Firestore ({firestore_id})")
        return ok

    # firestore_fallback -- مفيش صف Supabase نحدّثه أصلًا
    return firebase_service.update_recurring_reminder_last_sent(reminder["id"])


def delete_recurring_reminder_db(reminder_id):
    """
    حذف تذكير متكرر بالـ id بتاعه. بيدوّر الأول في Supabase (يغطي الحالة
    العادية وحالة الـ legacy ids اللي اتعملت قبل الـ pilot -- في الحالتين
    لو ملقهوش هيرجع لـ Firestore direct).
    """
    row = supabase_service.get_by_id(reminder_id)

    if row:
        ok = supabase_service.delete_by_id(reminder_id)
        firestore_id = row.get("firestore_id")
        if firestore_id:
            mirror_ok = firebase_service.delete_recurring_reminder_db(firestore_id)
            if not mirror_ok:
                logger.warning(f"⚠️ نجح الحذف في Supabase لكن فشل الـ mirror في Firestore ({firestore_id})")
        return ok

    logger.warning(f"⚠️ التذكير {reminder_id} مش موجود في Supabase، هجرب أمسحه من Firestore مباشرة")
    return firebase_service.delete_recurring_reminder_db(reminder_id)
