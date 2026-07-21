# -*- coding: utf-8 -*-
"""
⏰ خدمة الجدولة المتقدمة (APScheduler Manager)
- إدارة التذكيرات المتكررة
- دعم: يومي، كل ساعة، أيام محددة، أوقات محددة
"""

from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from utils.logger import logger
from utils.time_utils import now_cairo
from services.reminder_service import get_recurring_reminders

# Scheduler عام (سيتم ربطه من main.py)
scheduler_instance = None

def set_scheduler(scheduler):
    """ربط الـ scheduler الرئيسي"""
    global scheduler_instance
    scheduler_instance = scheduler
    logger.info("✅ تم ربط APScheduler في scheduler_service")

def add_daily_reminder(text, hour, minute=0, user_id=None):
    """
    إضافة تذكير يومي
    
    Args:
        text: نص التذكير
        hour: الساعة (0-23)
        minute: الدقيقة (0-59)
        user_id: معرّف المستخدم
    
    Returns:
        معرّف الـ job أو None
    """
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return None
    
    try:
        job_id = f"daily_{hour:02d}_{minute:02d}_{text[:20]}"
        
        def reminder_job():
            from bot import get_chat_id, bot
            chat_id = get_chat_id()
            if chat_id:
                try:
                    message = f"⏰ تذكير يومي: {text}"
                    bot.send_message(chat_id, message)
                    logger.info(f"✅ اتبعت تذكير يومي: {text}")
                except Exception as e:
                    logger.error(f"❌ خطأ في إرسال التذكير: {e}")
        
        job = scheduler_instance.add_job(
            reminder_job,
            'cron',
            hour=hour,
            minute=minute,
            id=job_id,
            name=f"تذكير يومي: {text}",
            replace_existing=True,
            misfire_grace_time=60
        )
        
        logger.info(f"✅ تذكير يومي: '{text}' الساعة {hour:02d}:{minute:02d}")
        return job_id
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة تذكير يومي: {e}")
        return None

def add_hourly_reminder(text, minute=0, user_id=None):
    """
    إضافة تذكير كل ساعة
    
    Args:
        text: نص التذكير
        minute: الدقيقة في كل ساعة (0-59)
        user_id: معرّف المستخدم
    
    Returns:
        معرّف الـ job أو None
    """
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return None
    
    try:
        job_id = f"hourly_{minute:02d}_{text[:20]}"
        
        def reminder_job():
            from bot import get_chat_id, bot
            chat_id = get_chat_id()
            if chat_id:
                try:
                    message = f"⏰ تذكير: {text}"
                    bot.send_message(chat_id, message)
                    logger.info(f"✅ اتبعت تذكير: {text}")
                except Exception as e:
                    logger.error(f"❌ خطأ في إرسال التذكير: {e}")
        
        job = scheduler_instance.add_job(
            reminder_job,
            'cron',
            minute=minute,
            id=job_id,
            name=f"تذكير كل ساعة: {text}",
            replace_existing=True,
            misfire_grace_time=60
        )
        
        logger.info(f"✅ تذكير كل ساعة: '{text}' في الدقيقة {minute:02d}")
        return job_id
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة تذكير كل ساعة: {e}")
        return None

def add_interval_reminder(text, days=1, hours=0, minutes=0, user_id=None):
    """
    إضافة تذكير كل فترة زمنية
    
    Args:
        text: نص التذكير
        days: عدد الأيام
        hours: عدد الساعات
        minutes: عدد الدقائق
        user_id: معرّف المستخدم
    
    Returns:
        معرّف الـ job أو None
    """
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return None
    
    try:
        job_id = f"interval_{days}d_{hours}h_{minutes}m_{text[:20]}"
        
        def reminder_job():
            from bot import get_chat_id, bot
            chat_id = get_chat_id()
            if chat_id:
                try:
                    message = f"⏰ تذكير: {text}"
                    bot.send_message(chat_id, message)
                    logger.info(f"✅ اتبعت تذكير: {text}")
                except Exception as e:
                    logger.error(f"❌ خطأ في إرسال التذكير: {e}")
        
        # حساب الثواني الكلي
        total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        
        job = scheduler_instance.add_job(
            reminder_job,
            'interval',
            seconds=total_seconds,
            id=job_id,
            name=f"تذكير كل {days}d {hours}h {minutes}m: {text}",
            replace_existing=True,
            misfire_grace_time=60
        )
        
        logger.info(f"✅ تذكير كل {days}d {hours}h {minutes}m: '{text}'")
        return job_id
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة تذكير الفترة: {e}")
        return None

def add_day_of_month_reminder(text, day, hour, minute=0, user_id=None):
    """
    إضافة تذكير في يوم محدد من الشهر (مثل 15 من كل شهر)
    
    Args:
        text: نص التذكير
        day: اليوم (1-31)
        hour: الساعة
        minute: الدقيقة
        user_id: معرّف المستخدم
    
    Returns:
        معرّف الـ job أو None
    """
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return None
    
    try:
        job_id = f"monthly_{day:02d}_{hour:02d}_{minute:02d}_{text[:20]}"
        
        def reminder_job():
            from bot import get_chat_id, bot
            chat_id = get_chat_id()
            if chat_id:
                try:
                    message = f"⏰ تذكير: {text}"
                    bot.send_message(chat_id, message)
                    logger.info(f"✅ اتبعت تذكير: {text}")
                except Exception as e:
                    logger.error(f"❌ خطأ في إرسال التذكير: {e}")
        
        job = scheduler_instance.add_job(
            reminder_job,
            'cron',
            day=day,
            hour=hour,
            minute=minute,
            id=job_id,
            name=f"تذكير يوم {day} من الشهر: {text}",
            replace_existing=True,
            misfire_grace_time=60
        )
        
        logger.info(f"✅ تذكير يوم {day} من الشهر الساعة {hour:02d}:{minute:02d}: '{text}'")
        return job_id
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة تذكير يومي الشهر: {e}")
        return None

def add_smart_loan_reminder(hour=22, minute=0, start_day=5, user_id=None):
    """
    تذكير ذكي شرطي للأقساط:
    - كل يوم بعد يوم start_day من الشهر (افتراضيًا يوم 5)، يفحص فعليًا
      أقساط الشهر الحالي غير المدفوعة
    - لو فيه أقساط متبقية، يبعت تذكير بقايمة الأقساط المحددة بأسمائها ومبالغها
    - لو كل الأقساط اتدفعت (أو لسه قبل يوم start_day)، ميبعتش أي حاجة خالص
    
    Args:
        hour: الساعة اللي يفحص فيها كل يوم (افتراضيًا 22 = 10 بالليل)
        minute: الدقيقة
        start_day: أول يوم في الشهر يبدأ يفحص من بعده (افتراضيًا 5)
        user_id: معرّف المستخدم (اختياري)
    
    Returns:
        معرّف الـ job أو None
    """
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return None
    
    try:
        job_id = "smart_loan_reminder"
        
        def reminder_job():
            from bot import get_chat_id, bot
            from services.loan_service import get_current_month_key, get_month_installments
            
            chat_id = get_chat_id()
            if not chat_id:
                return
            
            try:
                today = now_cairo()
                if today.day < start_day:
                    logger.info(f"⏭️ تذكير الأقساط: النهاردة يوم {today.day}، لسه قبل يوم {start_day}")
                    return
                
                month_key = get_current_month_key()
                items, total = get_month_installments(month_key)
                unpaid = [i for i in items if not i.get("paid")]
                
                if not unpaid:
                    logger.info("✅ تذكير الأقساط: كل الأقساط متدفوعة، مفيش حاجة تتبعت")
                    return
                
                lines = [f"- {i['program']}: {i['amount']} جنيه" for i in unpaid]
                unpaid_total = sum(i["amount"] for i in unpaid)
                message = (
                    f"💰 تذكير الأقساط (الشهر ده):\n\n" +
                    "\n".join(lines) +
                    f"\n\nالإجمالي المتبقي: {unpaid_total} جنيه"
                )
                bot.send_message(chat_id, message)
                logger.info(f"✅ اتبعت تذكير أقساط ذكي: {len(unpaid)} قسط متبقي")
                
            except Exception as e:
                logger.error(f"❌ خطأ في فحص تذكير الأقساط الذكي: {e}")
        
        job = scheduler_instance.add_job(
            reminder_job,
            'cron',
            hour=hour,
            minute=minute,
            id=job_id,
            name="تذكير ذكي شرطي للأقساط",
            replace_existing=True,
            misfire_grace_time=300
        )
        
        logger.info(f"✅ تذكير الأقساط الذكي شغال: كل يوم الساعة {hour:02d}:{minute:02d} بعد يوم {start_day}")
        return job_id
        
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة تذكير الأقساط الذكي: {e}")
        return None

def list_scheduled_jobs():
    """عرض جميع الـ jobs المجدولة"""
    if scheduler_instance is None:
        return []
    
    try:
        jobs = scheduler_instance.get_jobs()
        result = []
        for job in jobs:
            # استبعد reminder_checker (الوظيفة الداخلية)
            if job.id == 'reminder_checker':
                continue
            
            result.append({
                "معرّف": job.id,
                "الاسم": job.name,
                "الدالة": str(job.func),
                "المرة_القادمة": str(job.next_run_time)
            })
        return result
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الـ jobs: {e}")
        return []

def remove_scheduled_job(job_id):
    """حذف جob مجدول"""
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return False
    
    try:
        scheduler_instance.remove_job(job_id)
        logger.info(f"✅ تم حذف الـ job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حذف الـ job: {e}")
        return False

def pause_scheduled_job(job_id):
    """إيقاف job مجدول مؤقتاً"""
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return False
    
    try:
        job = scheduler_instance.get_job(job_id)
        if job:
            job.pause()
            logger.info(f"✅ تم إيقاف الـ job: {job_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ خطأ في إيقاف الـ job: {e}")
        return False

def resume_scheduled_job(job_id):
    """استئناف job مجدول"""
    if scheduler_instance is None:
        logger.error("❌ Scheduler مش متصل")
        return False
    
    try:
        job = scheduler_instance.get_job(job_id)
        if job:
            job.resume()
            logger.info(f"✅ تم استئناف الـ job: {job_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ خطأ في استئناف الـ job: {e}")
        return False
