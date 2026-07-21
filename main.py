# -*- coding: utf-8 -*-
"""
🚀 ADAM v1 — Main
=====================================================
نقطة الدخول الرئيسية.

Pipeline:
    Telegram Message
        ↓
    ADAM Runtime (9 مراحل)
        ↓
    Response
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger
from utils.time_utils import now_cairo

# ============================================================
# تهيئة الخدمات
# ============================================================

logger.info("=" * 50)
logger.info("🚀 ADAM v1 — Starting...")
logger.info("=" * 50)

# Firebase
from services.firebase_service import init_firebase
firebase_ok = init_firebase()
logger.info(f"{'✅' if firebase_ok else '❌'} Firebase")

# OpenAI
from services.openai_service import init_openai
openai_ok = init_openai()
logger.info(f"{'✅' if openai_ok else '❌'} OpenAI")

# Bot
from bot import bot, load_config, get_chat_id, set_chat_id, send_error_message
logger.info("✅ Telegram Bot")

# ============================================================
# تهيئة ADAM Core
# ============================================================

from adam_human_model import human_model
logger.info("✅ Human Model")

from adam_mind import adam_mind
logger.info("✅ ADAM Mind")

from adam_runtime import AdamRuntime
runtime = AdamRuntime(human_model, adam_mind)
logger.info("✅ ADAM Runtime")

# ============================================================
# Capabilities
# ============================================================

from services.claude_service import ask_claude_agentic, format_history_for_claude
from services.firebase_service import get_conversation_history, save_conversation
from services.memory_service import get_memory, update_memory

def claude_capability(execution):
    """Claude — يعالج الـ user requests"""
    text = execution.event.text
    chat_id = execution.event.chat_id

    # Context
    stored_history = get_conversation_history(chat_id, limit=50)
    recent_history = format_history_for_claude(stored_history, limit=15)
    memory_summary = get_memory(chat_id)

    reply = ask_claude_agentic(
        text,
        chat_id,
        conversation_history=recent_history,
        memory_summary=memory_summary
    )

    # حفظ المحادثة
    save_conversation(chat_id, text, reply)

    # تحديث الذاكرة
    if len(text) > 15 or len(reply) > 60:
        update_memory(chat_id, text, reply)

    return reply

def morning_brief_capability(execution):
    """Morning Brief — ADAM يفكر ويصيغ من تلقاء نفسه"""
    from morning_brief import generate_morning_brief
    chat_id = execution.event.chat_id
    return generate_morning_brief(str(chat_id))

def reminder_capability(execution):
    """إرسال تذكير"""
    return f"⏰ تذكير: {execution.event.metadata.get('text', '')}"

# تسجيل الـ Capabilities
runtime.register_capability("claude", claude_capability)
runtime.register_capability("morning_brief", morning_brief_capability)
runtime.register_capability("reminder", reminder_capability)
logger.info("✅ Capabilities registered")

# ============================================================
# Telegram Handlers
# ============================================================

@bot.message_handler(func=lambda message: (
    message.text is not None and
    not message.text.startswith('/')
))
def handle_message(message):
    """معالجة الرسائل النصية"""
    try:
        set_chat_id(message.chat.id)
        bot.send_chat_action(message.chat.id, 'typing')

        # ADAM Runtime — 9 مراحل
        execution = runtime.run(message)

        if execution.final_response:
            bot.reply_to(message, execution.final_response)
            logger.info(f"✅ ADAM responded | goal: {execution.execution_goal}")
        else:
            bot.reply_to(message, "❌ مش قادر أرد دلوقتي.")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        send_error_message(message, str(e))


@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    """معالجة الرسائل الصوتية"""
    try:
        set_chat_id(message.chat.id)
        bot.send_chat_action(message.chat.id, 'typing')

        from handlers.voice_handler import handle_voice_message
        handle_voice_message(message)
    except Exception as e:
        logger.error(f"❌ Voice error: {e}")
        bot.reply_to(message, "❌ مش قادر أسمع الصوت دلوقتي.")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """معالجة الصور"""
    try:
        set_chat_id(message.chat.id)
        from handlers.photo_handler import handle_photo_message
        handle_photo_message(message)
    except Exception as e:
        logger.error(f"❌ Photo error: {e}")
        bot.reply_to(message, "❌ مش قادر أشوف الصورة دلوقتي.")


@bot.message_handler(commands=['start'])
def handle_start(message):
    """أمر البداية"""
    set_chat_id(message.chat.id)
    name = human_model.get_name()
    bot.reply_to(message, f"أهلاً يا {name}! أنا ADAM — دماغك التاني. 🧠")


@bot.message_handler(commands=['backup'])
def handle_backup(message):
    """تشغيل الـ Backup يدوياً للاختبار"""
    try:
        set_chat_id(message.chat.id)
        bot.reply_to(message, "💾 بدأت الـ Backup... استنى ثوانٍ.")
        from services.backup_service import run_backup
        run_backup(bot=bot, chat_id=message.chat.id)
    except Exception as e:
        logger.error(f"❌ Manual backup error: {e}")
        bot.reply_to(message, f"❌ حصل خطأ: {e}")


# ============================================================
# Scheduler
# ============================================================

from apscheduler.schedulers.background import BackgroundScheduler
from services import scheduler_service

scheduler = BackgroundScheduler(timezone="Africa/Cairo")

def check_loans_job():
    """فحص الأقساط القريبة — كل يوم الساعة 9 صباحاً"""
    try:
        from services.loan_service import LoanService
        from utils.time_utils import now_cairo
        from datetime import timedelta

        chat_id = get_chat_id()
        if not chat_id:
            return

        loan_service = LoanService()
        installments = loan_service.get_month_installments()
        now = now_cairo()

        urgent = []
        for inst in installments:
            if inst.get("paid"):
                continue
            # لو القسط في الـ 3 أيام الجاية
            try:
                from datetime import datetime
                # الأقساط في أول الشهر عادةً
                days_remaining = inst.get("days_remaining", 999)
                if isinstance(days_remaining, (int, float)) and days_remaining <= 3:
                    urgent.append(inst)
            except:
                continue

        if urgent:
            lines = [f"- {i.get('program', '')}: {i.get('amount', '')} جنيه" for i in urgent]
            message = "⚠️ تنبيه أقساط قريبة:" + chr(10) + chr(10).join(lines)


            bot.send_message(chat_id, message)
            logger.info(f"✅ Loan alert sent: {len(urgent)} installments")

    except Exception as e:
        logger.error(f"❌ Loans check error: {e}")


def weekly_report_job():
    """تقرير أسبوعي كل جمعة الساعة 1 الظهر"""
    try:
        from morning_brief import generate_morning_brief
        from utils.time_utils import now_cairo

        chat_id = get_chat_id()
        if not chat_id:
            return

        now = now_cairo()
        ctx_prompt = f"""أنت ADAM — دماغ أحمد التاني.

دلوقتي نهاية الأسبوع ({now.strftime('%A %d/%m/%Y')}).

اكتب تقرير أسبوعي شامل لأحمد (بحورة) بالعامية المصرية:

- 📊 ملخص الأسبوع: إيه اللي اتعمل
- 💰 المصاريف والأقساط في الأسبوع ده
- 📌 المواعيد الجاية الأسبوع القادم
- ⚠️ أي تحذيرات أو حاجات محتاجة انتباه
- 🎯 توصية واحدة للأسبوع الجاي

اكتبه بأسلوب حر ومختلف كل أسبوع — مفيش قوالب."""

        from services.claude_service import ask_claude_agentic
        from services.memory_service import get_memory

        report = ask_claude_agentic(
            ctx_prompt,
            chat_id,
            conversation_history=[],
            memory_summary=get_memory(chat_id)
        )

        bot.send_message(chat_id, f"📊 التقرير الأسبوعي\n\n{report}")
        logger.info("✅ Weekly report sent")

    except Exception as e:
        logger.error(f"❌ Weekly report error: {e}")


def morning_brief_job():
    """Morning Brief الساعة 8"""
    try:
        chat_id = get_chat_id()
        if not chat_id:
            return
        execution = runtime.run_scheduled("morning_brief", chat_id)
        if execution.final_response:
            bot.send_message(chat_id, execution.final_response)
            logger.info("✅ Morning Brief sent")
    except Exception as e:
        logger.error(f"❌ Morning Brief error: {e}")

def check_reminders_job():
    """فحص التذكيرات كل 30 ثانية"""
    try:
        from services.reminder_service import (
            get_pending_local_reminders,
            mark_reminder_sent_locally
        )
        chat_id = get_chat_id()
        if not chat_id:
            return
        pending = get_pending_local_reminders()
        for index, reminder in pending:
            bot.send_message(chat_id, f"⏰ تذكير: {reminder['نص']}")
            mark_reminder_sent_locally(index)
    except Exception as e:
        logger.error(f"❌ Reminders error: {e}")

def check_recurring_reminders_job():
    """فحص التذكيرات المتكررة كل دقيقة"""
    try:
        from services.firebase_service import (
            get_active_recurring_reminders,
            update_recurring_reminder_last_sent
        )
        import time
        from datetime import datetime, timezone, timedelta

        chat_id = get_chat_id()
        if not chat_id:
            return

        reminders = get_active_recurring_reminders()
        now_ms = int(time.time() * 1000)

        for reminder in reminders:
            last_sent = reminder.get("last_sent")
            interval_type = reminder.get("interval_type", "daily")
            interval_value = reminder.get("interval_value", 1)

            intervals = {
                "daily": 24 * 60 * 60 * 1000,
                "weekly": 7 * 24 * 60 * 60 * 1000,
                "hourly": 60 * 60 * 1000,
                "custom_minutes": int(interval_value) * 60 * 1000
            }
            interval_ms = intervals.get(interval_type, 24 * 60 * 60 * 1000)

            should_send = (last_sent is None or (now_ms - last_sent) >= interval_ms)

            # لو في وقت محدد
            scheduled_hour = reminder.get("scheduled_hour")
            if scheduled_hour is not None and interval_type == "daily":
                cairo_tz = timezone(timedelta(hours=3))
                now_cairo_time = datetime.now(cairo_tz)
                should_send = (
                    should_send and
                    now_cairo_time.hour == scheduled_hour and
                    now_cairo_time.minute == reminder.get("scheduled_minute", 0)
                )

            if should_send:
                bot.send_message(chat_id, f"🔔 تذكير: {reminder['text']}")
                update_recurring_reminder_last_sent(reminder["id"])

    except Exception as e:
        logger.error(f"❌ Recurring reminders error: {e}")


def backup_job():
    """💾 Backup يومي لكل Firestore collections — الساعة 2:00 صباحاً"""
    try:
        from services.backup_service import run_backup
        chat_id = get_chat_id()
        run_backup(bot=bot, chat_id=chat_id)
    except Exception as e:
        logger.error(f"❌ Backup error: {e}")

# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("🤖 ADAM v1")
        logger.info(f"📅 {now_cairo().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"✅ Firebase: {'OK' if firebase_ok else 'FAIL'}")
        logger.info(f"✅ Human: {human_model.get_name()}")
        logger.info("=" * 50)

        load_config()

        # Scheduler
        scheduler.add_job(check_reminders_job, 'interval', seconds=30,
                         id='reminders', misfire_grace_time=10)
        scheduler.add_job(check_recurring_reminders_job, 'interval', minutes=1,
                         id='recurring', misfire_grace_time=30)
        scheduler.add_job(check_loans_job, 'cron', hour=9, minute=0,
                         id='loans_check', timezone='Africa/Cairo', misfire_grace_time=60)
        scheduler.add_job(morning_brief_job, 'cron', hour=8, minute=0,
                         id='morning', timezone='Africa/Cairo', misfire_grace_time=60)
        scheduler.add_job(weekly_report_job, 'cron', day_of_week='fri', hour=13, minute=0,
                         id='weekly_report', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(backup_job, 'cron', hour=2, minute=0,
                         id='daily_backup', timezone='Africa/Cairo', misfire_grace_time=300)

        scheduler_service.set_scheduler(scheduler)
        scheduler.start()
        logger.info("✅ Scheduler started")

        logger.info("🚀 ADAM v1 — Waiting for Ahmed...")
        logger.info("=" * 50)

        bot.infinity_polling(timeout=30, long_polling_timeout=30)

    except KeyboardInterrupt:
        logger.info("👋 ADAM stopped")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise
    finally:
        if scheduler.running:
            scheduler.shutdown()
