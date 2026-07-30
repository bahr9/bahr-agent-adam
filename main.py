# -*- coding: utf-8 -*-
"""
ADAM v1 -- Main
=====================================================
نقطة الدخول الرئيسية.

Pipeline:
    Telegram Message
        |
    ADAM Runtime (9 مراحل)
        |
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
logger.info("ADAM v1 -- Starting...")
logger.info("=" * 50)

# Firebase
from services.firebase_service import init_firebase
firebase_ok = init_firebase()
logger.info(("OK " if firebase_ok else "FAIL ") + "Firebase")

# OpenAI
from services.openai_service import init_openai
openai_ok = init_openai()
logger.info(("OK " if openai_ok else "FAIL ") + "OpenAI")

# Bot
from bot import bot, load_config, get_chat_id, set_chat_id, send_error_message, safe_send_message, get_main_keyboard, get_expenses_keyboard, get_projects_keyboard, get_reminders_keyboard, get_memory_keyboard, get_eye_expert_keyboard
logger.info("OK Telegram Bot")

# Command Handlers -- استيراد بيسجل الـ @bot.message_handler decorators بتاعة
# /save /tasks /done /clear /ideas /remind /remind_daily /remind_hourly
# /remind_monthly /schedule_list /schedule_remove /graph_list /graph_add
# /graph_edit /graph_delete. الاستيراد نفسه هو التسجيل -- من غيره الأوامر
# دي مسجلة في /help بس مش شغالة فعليًا.
import handlers.command_handler  # noqa: F401
logger.info("OK Command Handlers")

# ============================================================
# تهيئة ADAM Core
# ============================================================

from adam_mind import adam_mind
logger.info("OK ADAM Mind")

from executive_brain import ExecutiveBrain
executive_brain = ExecutiveBrain(adam_mind)
logger.info("OK Executive Brain")

from adam_runtime import AdamRuntime
runtime = AdamRuntime(executive_brain)
logger.info("OK ADAM Runtime")

# ============================================================
# Capabilities -- Startup Diagnostics (تشخيص النسخة المُحمَّلة فعليًا)
# =====================================================
# ده اللي بيرد على حوادث "الأداة الجديدة مش ظاهرة في /app" -- بيوضح فورًا
# وقت التشغيل: أي commit شغّال، مسار الملف الحقيقي المُحمَّل، وعدد وأسماء
# أدوات Self-State/Tool-Health المسجّلة فعليًا. لو /app لسه على نسخة قديمة،
# السطور دي هتوريها فورًا في اللوج بدل ما نكتشفها بالتخمين.
# ============================================================

def _detect_running_commit() -> str:
    import os
    commit = os.getenv("HEROKU_SLUG_COMMIT") or os.getenv("SOURCE_VERSION")
    if commit:
        return commit[:12]
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return "unknown (لا يوجد .git أو متغير بيئة نسخة في هذه البيئة)"


import services.claude_service as claude_service_module

_running_commit = _detect_running_commit()
_registered_tool_names = [t["name"] for t in claude_service_module.TOOLS]
_self_state_health_tools = [
    name for name in ("request_verified_expression", "get_adam_self_state", "get_self_diagnosis_report", "get_tools_health_status")
    if name in _registered_tool_names
]

logger.info("=" * 50)
logger.info("🔍 Startup Diagnostics")
logger.info("Commit/Version: " + _running_commit)
logger.info("claude_service loaded from: " + claude_service_module.__file__)
logger.info("Total registered tools: " + str(len(_registered_tool_names)))
if _self_state_health_tools:
    logger.info("Self-State/Tool-Health tools available: " + ", ".join(_self_state_health_tools))
else:
    logger.warning("⚠️ لا توجد أي أدوات Self-State/Tool-Health مسجّلة -- تأكد إن هذه النسخة محدّثة")
logger.info("=" * 50)

logger.info("OK Capabilities registered")

# ============================================================
# Telegram Handlers
# ============================================================

# ============================================================
# Keyboard Menu Handlers
# ============================================================

MENU_TRIGGERS = {
    "\u0627\u0644\u0645\u0635\u0627\u0631\u064a\u0641":  ("submenu_expenses",  get_expenses_keyboard),
    "\u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639":  ("submenu_projects",  get_projects_keyboard),
    "\u0627\u0644\u062a\u0630\u0643\u064a\u0631\u0627\u062a": ("submenu_reminders", get_reminders_keyboard),
    "\u0627\u0644\u0630\u0627\u0643\u0631\u0629":   ("submenu_memory",    get_memory_keyboard),
    "\u0627\u0644\u062e\u0628\u064a\u0631":    ("submenu_eye",       get_eye_expert_keyboard),
    "\u0627\u0644\u0637\u0642\u0633":     None,
}

@bot.message_handler(func=lambda message: (
    message.text is not None and
    len(message.text.strip().split()) <= 4 and
    any(t in message.text for t in MENU_TRIGGERS)
))
def handle_menu(message):
    """معالجة أزرار القائمة الرئيسية"""
    try:
        set_chat_id(message.chat.id)
        text = message.text

        for trigger, handler in MENU_TRIGGERS.items():
            if trigger in text:
                if handler is None:
                    if "\u0627\u0644\u0637\u0642\u0633" in text:
                        fake_msg = type("M", (), {"text": "\u0627\u0644\u0637\u0642\u0633 \u062f\u0644\u0648\u0642\u062a\u064a", "chat": type("C", (), {"id": message.chat.id})(), "from_user": message.from_user, "content_type": "text", "message_id": 0})()
                        response = runtime.run(fake_msg)
                        if response:
                            bot.send_message(message.chat.id, response)
                    return
                label, keyboard_func = handler
                bot.send_message(message.chat.id, "\u0627\u062e\u062a\u0627\u0631:", reply_markup=keyboard_func())
                return

    except Exception as e:
        logger.error("Menu error: " + str(e))

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """معالجة الـ Inline Keyboard callbacks"""
    try:
        from services import verified_expression
        chat_id = call.message.chat.id
        set_chat_id(chat_id)
        data = call.data

        bot.answer_callback_query(call.id)

        if data == "back_main":
            bot.send_message(chat_id, "\u0627\u0644\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629:", reply_markup=get_main_keyboard())

        elif data == "expenses_summary":
            bot.send_message(chat_id, "\u0645\u0644\u062e\u0635 \u0627\u0644\u0645\u0635\u0627\u0631\u064a\u0641")
            bot.send_message(chat_id, "\u062c\u0627\u0631\u064a...")
            fake_msg = type("M", (), {"text": "\u0645\u0644\u062e\u0635 \u0627\u0644\u0645\u0635\u0627\u0631\u064a\u0641", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "expenses_add":
            bot.send_message(chat_id, "\u0642\u0648\u0644\u064a: \u0635\u0631\u0641\u062a \u0643\u0627\u0645 \u062c\u0646\u064a\u0647 \u0648\u0639\u0644\u0649 \u0625\u064a\u0647\u061f")

        elif data == "loans_month":
            fake_msg = type("M", (), {"text": "\u0627\u0644\u0623\u0642\u0633\u0627\u0637 \u0627\u0644\u0634\u0647\u0631 \u062f\u0647", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "projects_status":
            fake_msg = type("M", (), {"text": "\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "projects_alerts":
            fake_msg = type("M", (), {"text": "\u062a\u0646\u0628\u064a\u0647\u0627\u062a \u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639 \u0627\u0644\u0645\u062a\u0623\u062e\u0631\u0629", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "reminders_list":
            fake_msg = type("M", (), {"text": "\u0627\u0639\u0631\u0636 \u0627\u0644\u062a\u0630\u0643\u064a\u0631\u0627\u062a", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "reminders_recurring":
            fake_msg = type("M", (), {"text": "\u0627\u0639\u0631\u0636 \u0627\u0644\u062a\u0630\u0643\u064a\u0631\u0627\u062a \u0627\u0644\u0645\u062a\u0643\u0631\u0631\u0629", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "memory_notes":
            fake_msg = type("M", (), {"text": "\u0622\u062e\u0631 \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "memory_graph":
            fake_msg = type("M", (), {"text": "\u0627\u0639\u0631\u0636 \u062e\u0631\u064a\u0637\u0629 \u0628\u062d\u0631", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "projects_deadlines":
            fake_msg = type("M", (), {"text": "\u0627\u0644\u0645\u0648\u0627\u0639\u064a\u062f \u0627\u0644\u062c\u0627\u064a\u0629 \u0644\u0644\u0645\u0634\u0627\u0631\u064a\u0639", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

        elif data == "reminders_new":
            bot.send_message(chat_id, "\u0642\u0648\u0644\u064a: \u0630\u0643\u0631\u0646\u064a \u0628\u0639\u062f \u0643\u0627\u0645 \u062f\u0642\u064a\u0642\u0629/\u0633\u0627\u0639\u0629 \u0648\u0628\u0625\u064a\u0647\u061f")

        elif data == "eye_expert_logs":
            fake_msg = type("M", (), {"text": "\u0622\u062e\u0631 \u0623\u0633\u0626\u0644\u0629 \u0639\u0645\u0644\u0627\u0621 \u0639\u064a\u0646 \u0627\u0644\u062e\u0628\u064a\u0631", "chat": type("C", (), {"id": chat_id})(), "from_user": type("U", (), {"id": chat_id, "first_name": "Ahmed"})(), "content_type": "text", "message_id": 0})()
            response = runtime.run(fake_msg)
            if response:
                response = verified_expression.verify_and_finalize(chat_id, response)
                bot.send_message(chat_id, response)

    except Exception as e:
        logger.error("Callback error: " + str(e))

@bot.message_handler(func=lambda message: (
    message.text is not None and
    not message.text.startswith('/') and
    (
        not any(t in message.text for t in MENU_TRIGGERS) or
        len(message.text.strip().split()) > 4
    )
))
def handle_message(message):
    """معالجة الرسائل النصية"""
    try:
        set_chat_id(message.chat.id)
        bot.send_chat_action(message.chat.id, 'typing')

        # ADAM Runtime -> Executive Brain
        response = runtime.run(message)

        if response:
            from services import verified_expression
            response = verified_expression.verify_and_finalize(message.chat.id, response)
            bot.reply_to(message, response, reply_markup=get_main_keyboard())
            logger.info("OK ADAM responded")
        else:
            bot.reply_to(message, "\u274c \u0645\u0634 \u0642\u0627\u062f\u0631 \u0623\u0631\u062f \u062f\u0644\u0648\u0642\u062a\u064a.")

    except Exception as e:
        logger.error("Error: " + str(e))
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
        logger.error("Voice error: " + str(e))
        bot.reply_to(message, "\u274c \u0645\u0634 \u0642\u0627\u062f\u0631 \u0623\u0633\u0645\u0639 \u0627\u0644\u0635\u0648\u062a \u062f\u0644\u0648\u0642\u062a\u064a.")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """معالجة الصور"""
    try:
        set_chat_id(message.chat.id)
        from handlers.photo_handler import handle_photo_message
        handle_photo_message(message)
    except Exception as e:
        logger.error("Photo error: " + str(e))
        bot.reply_to(message, "\u274c \u0645\u0634 \u0642\u0627\u062f\u0631 \u0623\u0634\u0648\u0641 \u0627\u0644\u0635\u0648\u0631\u0629 \u062f\u0644\u0648\u0642\u062a\u064a.")


@bot.message_handler(content_types=['document'])
def handle_document(message):
    """معالجة الملفات (PDF, DOCX, HTML, TXT)"""
    try:
        set_chat_id(message.chat.id)
        from handlers.document_handler import handle_document_message
        handle_document_message(message)
    except Exception as e:
        logger.error("Document error: " + str(e))
        bot.reply_to(message, "\u274c \u0645\u0634 \u0642\u0627\u062f\u0631 \u0623\u0642\u0631\u0627 \u0627\u0644\u0645\u0644\u0641 \u062f\u0644\u0648\u0642\u062a\u064a.")


@bot.message_handler(commands=['start'])
def handle_start(message):
    """أمر البداية"""
    set_chat_id(message.chat.id)
    from services.firebase_service import get_human_model_display_name
    name = get_human_model_display_name()
    bot.reply_to(message, "\u0623\u0647\u0644\u0627\u064b \u064a\u0627 " + name + "! \u0623\u0646\u0627 ADAM -- \u062f\u0645\u0627\u063a\u0643 \u0627\u0644\u062a\u0627\u0646\u064a.")


@bot.message_handler(commands=['backup'])
def handle_backup(message):
    """تشغيل الـ Backup يدوياً للاختبار"""
    try:
        set_chat_id(message.chat.id)
        bot.reply_to(message, "\u062f\u0628\u062f\u0623\u062a \u0627\u0644\u0640 Backup... \u0627\u0633\u062a\u0646\u0649 \u062b\u0648\u0627\u0646.")
        from services.backup_service import run_backup
        run_backup(bot=bot, chat_id=message.chat.id)
    except Exception as e:
        logger.error("Manual backup error: " + str(e))
        bot.reply_to(message, "\u062d\u0635\u0644 \u062e\u0637\u0623: " + str(e))


# ============================================================
# Scheduler
# ============================================================

from apscheduler.schedulers.background import BackgroundScheduler
from services import scheduler_service

scheduler = BackgroundScheduler(timezone="Africa/Cairo")

def check_loans_job():
    """فحص الأقساط القريبة -- كل يوم الساعة 9 صباحاً"""
    try:
        from services.loan_service import get_month_installments, get_current_month_key
        from utils.time_utils import now_cairo

        chat_id = get_chat_id()
        if not chat_id:
            return

        month_key = get_current_month_key()
        installments, total = get_month_installments(month_key)

        urgent = [i for i in installments if not i.get("paid")]

        if urgent:
            lines = ["- " + i.get("program", "") + ": " + str(i.get("amount", "")) + " \u062c\u0646\u064a\u0647"
                     for i in urgent]
            message = "\u062a\u0646\u0628\u064a\u0647 \u0627\u0642\u0633\u0627\u0637 \u0627\u0644\u0634\u0647\u0631 \u062f\u0647:" + chr(10) + chr(10).join(lines)
            message += chr(10) + "\u0627\u0644\u0627\u062c\u0645\u0627\u0644\u064a: " + str(total) + " \u062c\u0646\u064a\u0647"
            bot.send_message(chat_id, message)
            logger.info("OK Loan alert sent: " + str(len(urgent)) + " installments")
        else:
            logger.info("OK Loans check: all paid")

    except Exception as e:
        logger.error("Loans check error: " + str(e))


def self_state_active_check_job():
    """
    فحص Self-State للتعبير الفعال (Active) -- Stage 6/7.
    """
    try:
        from services import self_state_engine, decision_engine, verified_expression

        chat_id = get_chat_id()
        if not chat_id:
            return

        self_state = self_state_engine.compute_self_state()
        decisions = decision_engine.decide_expression(self_state)

        for dimension, decision in decisions.items():
            if decision["mode"] == "active":
                verified_expression.send_active_expression(dimension, decision["level"], chat_id)

    except Exception as e:
        logger.error("Self-State active check error: " + str(e))


def tool_health_check_job():
    """
    فحص صحة الأدوات (Runtime Capabilities & Tool Health V1) -- كل ساعة، نفس
    نمط self_state_active_check_job بالظبط. صفر LLM: heartbeat (safe probes
    بس) -> تقييم حتمي -> تنبيه لو DEGRADED دخل/اتغيّر سببه/اتعافى.
    """
    try:
        from services import tool_health_heartbeat, tool_health_engine, tool_health_alerts

        chat_id = get_chat_id()
        if not chat_id:
            return

        tool_health_heartbeat.run_heartbeat()
        evaluations = tool_health_engine.evaluate_all_tools()
        tool_health_alerts.maybe_alert(evaluations, lambda text: bot.send_message(chat_id, text))

    except Exception as e:
        logger.error("Tool health check error: " + str(e))


def project_status_check_job():
    """
    فحص حالة مشاريع Bahr OS (delayed/suspended) كل ساعة -- نفس نمط
    tool_health_check_job بالظبط. صفر LLM: قراءة مباشرة + مقارنة حالة سابقة
    -> تنبيه بس عند انتقال حقيقي (دخول/خروج من حالة مقلقة).
    """
    try:
        from services import project_status_alerts

        chat_id = get_chat_id()
        if not chat_id:
            return

        project_status_alerts.check_project_status_alerts(
            lambda text: bot.send_message(chat_id, text)
        )

    except Exception as e:
        logger.error("Project status check error: " + str(e))


def urgent_deadlines_check_job():
    """
    تنبيه سريع (كل ساعة) للمواعيد اللي هتيجي خلال 3 أيام -- تكملة لـ Morning
    Brief اليومي، مش بديل عنه.
    """
    try:
        from services import deadline_alerts

        chat_id = get_chat_id()
        if not chat_id:
            return

        deadline_alerts.check_urgent_deadline_alerts(
            str(chat_id), lambda text: bot.send_message(chat_id, text)
        )

    except Exception as e:
        logger.error("Urgent deadlines check error: " + str(e))


def stale_tasks_check_job():
    """
    تذكير يومي بالمهام (/save) اللي لسه معلقة من أكتر من أسبوع -- مبادرة
    آدم من نفسه، من غير ما ينتظر يُسأل عنها.
    """
    try:
        from services import task_service

        chat_id = get_chat_id()
        if not chat_id:
            return

        stale = task_service.get_stale_tasks(days=7)
        if not stale:
            return

        lines = [f"- {t['نص']}" for t in stale[:10]]
        message = f"📋 عندك {len(stale)} مهمة من /save لسه معلقة من فوق أسبوع:\n\n" + "\n".join(lines)
        bot.send_message(chat_id, message)
        logger.info(f"OK Stale tasks reminder sent: {len(stale)} tasks")

    except Exception as e:
        logger.error("Stale tasks check error: " + str(e))


def agent_task_completion_check_job():
    """
    فحص دوري (كل 10 دقايق) للتاسكات اللي أنظمة تانية (مداد دلوقتي) خلّصتها
    (done/failed) ولسه محدش بلّغ أحمد بيها. مهم: مش بيبلّغ 'تم' على كلام
    النظام التاني بس -- بيتحقق فعليًا (verify_task_completion) من الدليل
    قبل ما يقول لأحمد إن التنفيذ اتأكد.
    """
    try:
        from services import agent_orchestration

        chat_id = get_chat_id()
        if not chat_id:
            return

        for task in agent_orchestration.get_unreported_completed_tasks():
            status = task.get("status")
            target = task.get("target", "")
            action = task.get("action", "")

            if status == "done":
                check = agent_orchestration.verify_task_completion(task)
                if check["verified"]:
                    text = f"✅ {target} خلّص التاسك: {action}\n{check['reason']}"
                else:
                    text = (
                        f"⚠️ {target} قال إنه خلّص التاسك ({action})، لكن التحقق المستقل فشل:\n"
                        f"{check['reason']}\n-- محتاج مراجعة يدوية."
                    )
            else:
                summary = (task.get("result") or {}).get("summary", "")
                text = f"❌ {target} فشل في تنفيذ التاسك: {action}\n{summary}"

            bot.send_message(chat_id, text)
            agent_orchestration.mark_task_reported(task.get("task_id"))
            logger.info(f"OK Agent task reported: {task.get('task_id')} ({status})")

    except Exception as e:
        logger.error("Agent task completion check error: " + str(e))


def stale_agent_tasks_check_job():
    """
    تنبيه يومي بالتاسكات اللي آدم بعتها لأنظمة تانية (Hope/مداد/عين الخبير)
    ولسه معلّقة (pending/in_progress) من فوق 3 أيام -- المرحلة 1 من
    الأوركسترا، "يبعت ويتابع" مش "يبعت وينسى".
    """
    try:
        from services import agent_orchestration

        chat_id = get_chat_id()
        if not chat_id:
            return

        stale = agent_orchestration.list_stale_agent_tasks(days=3)
        if not stale:
            return

        lines = [f"- [{t.get('target')}] {t.get('action')} (اتسجل: {t.get('created_at', '')[:10]})" for t in stale[:10]]
        message = f"🕸️ عندك {len(stale)} تاسك معلّق لأنظمة تانية من فوق 3 أيام:\n\n" + "\n".join(lines)
        bot.send_message(chat_id, message)
        logger.info(f"OK Stale agent-tasks reminder sent: {len(stale)} tasks")

    except Exception as e:
        logger.error("Stale agent-tasks check error: " + str(e))


def weekly_report_job():
    """تقرير أسبوعي كل جمعة الساعة 1 الظهر"""
    try:
        from morning_brief import generate_morning_brief
        from utils.time_utils import now_cairo

        chat_id = get_chat_id()
        if not chat_id:
            return

        now = now_cairo()
        ctx_prompt = (
            "\u0623\u0646\u062a ADAM -- \u062f\u0645\u0627\u063a \u0623\u062d\u0645\u062f \u0627\u0644\u062a\u0627\u0646\u064a.\n\n"
            "\u062f\u0644\u0648\u0642\u062a\u064a \u0646\u0647\u0627\u064a\u0629 \u0627\u0644\u0623\u0633\u0628\u0648\u0639 (" + now.strftime('%A %d/%m/%Y') + ").\n\n"
            "\u0627\u0643\u062a\u0628 \u062a\u0642\u0631\u064a\u0631 \u0623\u0633\u0628\u0648\u0639\u064a \u0634\u0627\u0645\u0644 \u0644\u0623\u062d\u0645\u062f (\u0628\u062d\u0648\u0631\u0629) \u0628\u0627\u0644\u0639\u0627\u0645\u064a\u0629 \u0627\u0644\u0645\u0635\u0631\u064a\u0629:\n\n"
            "- \u0645\u0644\u062e\u0635 \u0627\u0644\u0623\u0633\u0628\u0648\u0639: \u0625\u064a\u0647 \u0627\u0644\u0644\u064a \u0627\u062a\u0639\u0645\u0644\n"
            "- \u0627\u0644\u0645\u0635\u0627\u0631\u064a\u0641 \u0648\u0627\u0644\u0623\u0642\u0633\u0627\u0637 \u0641\u064a \u0627\u0644\u0623\u0633\u0628\u0648\u0639 \u062f\u0647\n"
            "- \u0627\u0644\u0645\u0648\u0627\u0639\u064a\u062f \u0627\u0644\u062c\u0627\u064a\u0629 \u0627\u0644\u0623\u0633\u0628\u0648\u0639 \u0627\u0644\u0642\u0627\u062f\u0645\n"
            "- \u0623\u064a \u062a\u062d\u0630\u064a\u0631\u0627\u062a \u0623\u0648 \u062d\u0627\u062c\u0627\u062a \u0645\u062d\u062a\u0627\u062c\u0629 \u0627\u0646\u062a\u0628\u0627\u0647\n"
            "- \u062a\u0648\u0635\u064a\u0629 \u0648\u0627\u062d\u062f\u0629 \u0644\u0644\u0623\u0633\u0628\u0648\u0639 \u0627\u0644\u062c\u0627\u064a\n\n"
            "\u0627\u0643\u062a\u0628\u0647 \u0628\u0623\u0633\u0644\u0648\u0628 \u062d\u0631 \u0648\u0645\u062e\u062a\u0644\u0641 \u0643\u0644 \u0623\u0633\u0628\u0648\u0639 -- \u0645\u0641\u064a\u0634 \u0642\u0648\u0627\u0644\u0628."
        )

        from services.claude_service import ask_claude_agentic
        from services.memory_service import get_memory

        report = ask_claude_agentic(
            ctx_prompt,
            chat_id,
            conversation_history=[],
            memory_summary=get_memory(chat_id)
        )

        from services import verified_expression
        report = verified_expression.verify_and_finalize(chat_id, report)

        bot.send_message(chat_id, "\u062a\u0642\u0631\u064a\u0631 \u0627\u0644\u0623\u0633\u0628\u0648\u0639\u064a\n\n" + report)
        logger.info("OK Weekly report sent")

    except Exception as e:
        logger.error("Weekly report error: " + str(e))


def morning_brief_job():
    """Morning Brief الساعة 8"""
    try:
        chat_id = get_chat_id()
        if not chat_id:
            return
        response = runtime.run_scheduled("morning_brief", chat_id)
        if response:
            bot.send_message(chat_id, response)
            logger.info("OK Morning Brief sent")
    except Exception as e:
        logger.error("Morning Brief error: " + str(e))

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
            bot.send_message(chat_id, "\u23f0 \u062a\u0630\u0643\u064a\u0631: " + reminder['\u0646\u0635'])
            mark_reminder_sent_locally(index)
    except Exception as e:
        logger.error("Reminders error: " + str(e))

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
                bot.send_message(chat_id, "\u0631\u0633\u0627\u0644\u0629: " + reminder['text'])
                update_recurring_reminder_last_sent(reminder["id"])

    except Exception as e:
        logger.error("Recurring reminders error: " + str(e))


def backup_job():
    """Backup يومي لكل Firestore collections -- الساعة 2:00 صباحاً"""
    try:
        from services.backup_service import run_backup
        chat_id = get_chat_id()
        run_backup(bot=bot, chat_id=chat_id)
    except Exception as e:
        logger.error("Backup error: " + str(e))


# ============================================================
# Flask -- Eye Expert Logging Endpoint
# ============================================================

from flask import Flask, request, jsonify
from threading import Thread

flask_app = Flask(__name__)

@flask_app.route("/log-eye-expert", methods=["POST"])
def log_eye_expert():
    """استقبال logs من Make.com وحفظها في Firestore"""
    try:
        import os
        secret = os.getenv("EYE_EXPERT_SECRET", "")
        token  = request.headers.get("X-Secret-Token", "") or request.args.get("token", "")
        if secret and token != secret:
            return jsonify({"status": "unauthorized"}), 401

        data = request.get_json(force=True, silent=True) or {}

        question   = data.get("question", "")
        answer     = data.get("answer", "")
        client     = data.get("client", "")
        source     = data.get("source", "whatsapp")

        if not question and not answer:
            return jsonify({"status": "error", "message": "question و answer مطلوبين"}), 400

        from services.firebase_service import save_ain_al_khabeer_log as save_eye_expert_log
        ok = save_eye_expert_log({
            "question": question,
            "answer":   answer,
            "client":   client,
            "source":   source,
        })

        if ok:
            logger.info("Eye Expert log saved | client: " + client + " | source: " + source)
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error", "message": "فشل الحفظ في Firestore"}), 500

    except Exception as e:
        logger.error("Eye Expert log error: " + str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@flask_app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({"status": "ok", "service": "ADAM"}), 200

def run_flask():
    """تشغيل Flask في thread منفصل"""
    flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("ADAM v1")
        logger.info("Date: " + now_cairo().strftime('%Y-%m-%d %H:%M:%S'))
        logger.info("Firebase: " + ("OK" if firebase_ok else "FAIL"))
        from services.firebase_service import get_human_model_display_name
        logger.info("Human: " + get_human_model_display_name())
        logger.info("=" * 50)

        load_config()

        # Scheduler
        scheduler.add_job(check_reminders_job, 'interval', seconds=30,
                         id='reminders', misfire_grace_time=10)
        scheduler.add_job(check_recurring_reminders_job, 'interval', minutes=1,
                         id='recurring', misfire_grace_time=30)
        scheduler.add_job(check_loans_job, 'cron', hour=9, minute=0,
                         id='loans_check', timezone='Africa/Cairo', misfire_grace_time=60)
        scheduler.add_job(self_state_active_check_job, 'interval', hours=1,
                         id='self_state_active_check', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(tool_health_check_job, 'interval', hours=1,
                         id='tool_health_check', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(project_status_check_job, 'interval', hours=1,
                         id='project_status_check', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(urgent_deadlines_check_job, 'interval', hours=1,
                         id='urgent_deadlines_check', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(agent_task_completion_check_job, 'interval', minutes=10,
                         id='agent_task_completion_check', timezone='Africa/Cairo', misfire_grace_time=120)
        scheduler.add_job(stale_tasks_check_job, 'cron', hour=20, minute=0,
                         id='stale_tasks_check', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(stale_agent_tasks_check_job, 'cron', hour=20, minute=5,
                         id='stale_agent_tasks_check', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(morning_brief_job, 'cron', hour=8, minute=0,
                         id='morning', timezone='Africa/Cairo', misfire_grace_time=60)
        scheduler.add_job(weekly_report_job, 'cron', day_of_week='fri', hour=13, minute=0,
                         id='weekly_report', timezone='Africa/Cairo', misfire_grace_time=300)
        scheduler.add_job(backup_job, 'cron', hour=2, minute=0,
                         id='daily_backup', timezone='Africa/Cairo', misfire_grace_time=300)

        scheduler_service.set_scheduler(scheduler)
        scheduler.start()
        logger.info("OK Scheduler started")

        # Flask في thread منفصل
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("OK Flask endpoint started on port 8080")

        logger.info("ADAM v1 -- Waiting for Ahmed...")
        logger.info("=" * 50)

        bot.infinity_polling(timeout=30, long_polling_timeout=30)

    except KeyboardInterrupt:
        logger.info("ADAM stopped")
    except Exception as e:
        logger.error("Fatal error: " + str(e))
        raise
    finally:
        if scheduler.running:
            scheduler.shutdown()
