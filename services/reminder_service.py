# -*- coding: utf-8 -*-
"""
⏰ خدمة التذكيرات
- إضافة، جلب، وإرسال التذكيرات
- معالجة المخزن المحلي والـ Firestore
"""

import json
import os
from datetime import datetime, timedelta
from utils.logger import logger
from utils.time_utils import now_cairo
from services.firebase_service import (
    save_reminder as firebase_save_reminder,
    get_pending_reminders as firebase_get_pending_reminders,
    mark_reminder_sent as firebase_mark_reminder_sent
)
from config import DATA_FILE

# ملف التذكيرات المحلي (backup)
second_brain = {"تذكيرات": []}

def load_local_reminders():
    """تحميل التذكيرات من الملف المحلي"""
    global second_brain
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                second_brain = data
                if "تذكيرات" not in second_brain:
                    second_brain["تذكيرات"] = []
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل التذكيرات: {e}")
            second_brain = {"تذكيرات": []}

def save_local_reminders():
    """حفظ التذكيرات في الملف المحلي"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(second_brain, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ التذكيرات: {e}")

# تحميل البيانات عند الاستيراد
load_local_reminders()

def add_reminder(text, send_at_dt, user_id=None):
    """
    إضافة تذكير جديد
    
    Args:
        text: نص التذكير
        send_at_dt: datetime للوقت المطلوب
        user_id: معرّف المستخدم (اختياري)
    
    Returns:
        True إذا نجح، False إذا فشل
    """
    try:
        # حفظ محلي
        second_brain["تذكيرات"].append({
            "نص": text,
            "وقت_الإرسال": send_at_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "تم_الإرسال": False
        })
        save_local_reminders()
        
        # حفظ في Firestore
        if user_id:
            firebase_save_reminder(
                user_id,
                text,
                int(send_at_dt.timestamp() * 1000)
            )
        
        logger.info(f"⏰ تذكير جديد: '{text}' في {send_at_dt.strftime('%Y-%m-%d %H:%M')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة التذكير: {e}")
        return False

def get_pending_local_reminders():
    """جلب التذكيرات المعلقة من الملف المحلي"""
    try:
        now = now_cairo()
        # المُخزَّن بدون معلومات timezone (naive)، فلازم نقارن بنفس النوع
        now_naive = now.replace(tzinfo=None) if now.tzinfo else now
        pending = []
        
        for i, reminder in enumerate(second_brain.get("تذكيرات", [])):
            if reminder.get("تم_الإرسال"):
                continue
            
            try:
                send_at = datetime.strptime(reminder["وقت_الإرسال"], "%Y-%m-%d %H:%M:%S")
                if send_at <= now_naive:
                    pending.append((i, reminder))
            except Exception as e:
                logger.warning(f"⚠️ خطأ في قراءة التذكير: {e}")
        
        return pending
        
    except Exception as e:
        logger.error(f"❌ خطأ في جلب التذكيرات: {e}")
        return []

def mark_reminder_sent_locally(index):
    """تعليم التذكير كـ مُرسل (محلياً)"""
    try:
        if 0 <= index < len(second_brain["تذكيرات"]):
            second_brain["تذكيرات"][index]["تم_الإرسال"] = True
            save_local_reminders()
            return True
    except Exception as e:
        logger.error(f"❌ خطأ في تعديل التذكير: {e}")
    return False

def check_and_send_reminders(bot_callback):
    """
    فحص والتذكيرات المستحقة وإرسالها
    
    Args:
        bot_callback: دالة لإرسال الرسالة (من البوت)
    """
    try:
        pending = get_pending_local_reminders()
        
        for index, reminder in pending:
            try:
                # إرسال التذكير
                message = f"⏰ تذكير: {reminder['نص']}"
                
                # قد تحتاج إلى chat_id هنا - يفترض أنك تمرره من البوت
                # bot_callback(chat_id, message)
                
                # تعليم كـ مُرسل
                mark_reminder_sent_locally(index)
                logger.info(f"✅ اتبعت تذكير: '{reminder['نص']}'")
                
            except Exception as e:
                logger.error(f"❌ خطأ في إرسال التذكير: {e}")
                
    except Exception as e:
        logger.error(f"❌ خطأ في فحص التذكيرات: {e}")

def clear_old_reminders(days=7):
    """حذف التذكيرات القديمة (أكثر من X أيام)"""
    try:
        now = now_cairo()
        cutoff = now - timedelta(days=days)
        
        new_reminders = []
        for reminder in second_brain.get("تذكيرات", []):
            try:
                send_at = datetime.strptime(reminder["وقت_الإرسال"], "%Y-%m-%d %H:%M:%S")
                if send_at >= cutoff:
                    new_reminders.append(reminder)
            except:
                new_reminders.append(reminder)
        
        second_brain["تذكيرات"] = new_reminders
        save_local_reminders()
        logger.info(f"🧹 تم حذف {len(second_brain['تذكيرات']) - len(new_reminders)} تذكيرات قديم")
        
    except Exception as e:
        logger.error(f"❌ خطأ في حذف التذكيرات القديمة: {e}")

def get_reminder_stats():
    """إحصائيات التذكيرات"""
    return {
        "total": len(second_brain.get("تذكيرات", [])),
        "sent": len([r for r in second_brain.get("تذكيرات", []) if r.get("تم_الإرسال")]),
        "pending": len([r for r in second_brain.get("تذكيرات", []) if not r.get("تم_الإرسال")])
    }

# ============================================================
# 🆕 دوال جدولة متقدمة (للاستخدام مع APScheduler)
# ============================================================

def add_recurring_reminder(text, schedule_type, time_value=None, user_id=None):
    """
    إضافة تذكير متكرر
    
    Args:
        text: نص التذكير
        schedule_type: نوع الجدولة ('daily', 'hourly', 'every_x_days', 'specific_time')
        time_value: قيمة إضافية حسب النوع
          - 'daily': الساعة (مثلاً 10 للساعة 10 صباحاً)
          - 'hourly': None
          - 'every_x_days': عدد الأيام (مثلاً 3)
          - 'specific_time': النص مباشرة (مثلاً "19:30")
        user_id: معرّف المستخدم
    
    Returns:
        معرّف التذكير أو None إذا فشل
    """
    try:
        reminder_id = f"recurring_{len(second_brain.get('تذكيرات_متكررة', []))}"
        
        if "تذكيرات_متكررة" not in second_brain:
            second_brain["تذكيرات_متكررة"] = []
        
        second_brain["تذكيرات_متكررة"].append({
            "معرّف": reminder_id,
            "نص": text,
            "نوع_الجدولة": schedule_type,
            "قيمة_الوقت": time_value,
            "تاريخ_الإنشاء": now_cairo().strftime("%Y-%m-%d %H:%M:%S"),
            "مفعّل": True
        })
        
        save_local_reminders()
        logger.info(f"⏰ تذكير متكرر جديد: '{text}' ({schedule_type})")
        return reminder_id
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة تذكير متكرر: {e}")
        return None

def get_recurring_reminders():
    """جلب جميع التذكيرات المتكررة"""
    return second_brain.get("تذكيرات_متكررة", [])

def disable_recurring_reminder(reminder_id):
    """تعطيل تذكير متكرر"""
    try:
        for reminder in second_brain.get("تذكيرات_متكررة", []):
            if reminder.get("معرّف") == reminder_id:
                reminder["مفعّل"] = False
                save_local_reminders()
                logger.info(f"✅ تم تعطيل التذكير: {reminder_id}")
                return True
        return False
    except Exception as e:
        logger.error(f"❌ خطأ في تعطيل التذكير: {e}")
        return False

def delete_recurring_reminder(reminder_id):
    """حذف تذكير متكرر"""
    try:
        if "تذكيرات_متكررة" not in second_brain:
            return False
        
        second_brain["تذكيرات_متكررة"] = [
            r for r in second_brain["تذكيرات_متكررة"]
            if r.get("معرّف") != reminder_id
        ]
        save_local_reminders()
        logger.info(f"✅ تم حذف التذكير: {reminder_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حذف التذكير: {e}")
        return False
