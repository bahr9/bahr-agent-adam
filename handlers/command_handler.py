# -*- coding: utf-8 -*-
"""
📋 معالج الأوامر الصريحة
- المهام: /save /tasks /done /clear
- الأفكار: /ideas
- التذكيرات: /remind /remind_time
- الجراف: /graph_list /graph_add /graph_edit /graph_delete
"""

import re
import time as time_module
from bot import bot, send_error_message, set_chat_id, get_reminder_time, set_reminder_time
from utils.logger import logger
from utils.time_utils import parse_time_input, now_cairo
from services.task_service import (
    add_task, get_all_tasks, mark_task_done, clear_all_tasks,
    add_idea, get_recent_ideas, clear_all_ideas
)
from services.reminder_service import add_reminder
from services.firebase_service import (
    graph_add_node, graph_edit_node, graph_delete_node, graph_list_nodes
)

VALID_CATEGORIES = ["project", "team", "task", "issue", "topic", "hub", "client", "site", "office"]

def make_node_id_from_label(label):
    """تحويل الاسم لـ ID صالح للاستخدام في Firestore"""
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", label.strip()).strip("-").lower()
    return f"bot-{slug}-{int(time_module.time())}"

# ============================================================
# 📋 أوامر المهام
# ============================================================

@bot.message_handler(commands=['save'])
def save_task_command(message):
    """حفظ مهمة جديدة"""
    try:
        set_chat_id(message.chat.id)
        task_text = message.text.replace('/save', '', 1).strip()
        
        if not task_text:
            bot.reply_to(message, "❌ اكتب المهمة.\n\nمثال: /save أغير لون المطبخ")
            return
        
        add_task(task_text)
        bot.reply_to(message, f"✅ تم الحفظ!\n\n📌 {task_text}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /save: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['tasks'])
def show_tasks_command(message):
    """عرض كل المهام"""
    try:
        tasks = get_all_tasks()
        
        if not tasks:
            bot.reply_to(message, "📭 مفيش مهام مسجلة.")
            return
        
        lines = []
        for i, task in enumerate(tasks, 1):
            status = "✅" if task.get("تم") else "⏳"
            lines.append(f"{i}. {status} {task['نص']}")
        
        bot.reply_to(message, "📋 مهامك:\n\n" + "\n".join(lines) + "\n\n🔹 استخدم /done رقم لتأكيد الإنجاز.")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /tasks: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['done'])
def mark_done_command(message):
    """تأكيد إنجاز مهمة"""
    try:
        num_text = message.text.replace('/done', '', 1).strip()
        
        if not num_text:
            bot.reply_to(message, "❌ اكتب رقم المهمة.\n\nمثال: /done 1")
            return
        
        task_num = int(num_text)
        ok, msg = mark_task_done(task_num)
        
        if ok:
            bot.reply_to(message, f"🎉 أحسن حاجة!\n\n✅ تم إنجاز: {msg}")
        else:
            bot.reply_to(message, f"❌ {msg}")
        
    except ValueError:
        bot.reply_to(message, "❌ اكتب رقم صحيح.\n\nمثال: /done 2")
    except Exception as e:
        logger.error(f"❌ خطأ في /done: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['clear'])
def clear_command(message):
    """مسح كل المهام"""
    try:
        clear_all_tasks()
        bot.reply_to(message, "🧹 تم مسح كل المهام.")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /clear: {e}")
        send_error_message(message, str(e))

# ============================================================
# 💡 أوامر الأفكار
# ============================================================

@bot.message_handler(commands=['ideas'])
def show_ideas_command(message):
    """عرض آخر الأفكار المسجلة"""
    try:
        ideas = get_recent_ideas(limit=10)
        
        if not ideas:
            bot.reply_to(message, "💭 مفيش أفكار مسجلة.")
            return
        
        lines = [f"{i}. {idea['نص']}" for i, idea in enumerate(ideas, 1)]
        bot.reply_to(message, "💡 آخر أفكارك:\n\n" + "\n".join(lines))
        
    except Exception as e:
        logger.error(f"❌ خطأ في /ideas: {e}")
        send_error_message(message, str(e))

# ============================================================
# 📋 أوامر استبيانات العملاء (brief.html → Supabase)
# ============================================================

@bot.message_handler(commands=['briefs'])
def show_client_briefs_command(message):
    """عرض الاستبيانات الجديدة وتعليمها seen.

    None من الخدمة = Supabase مش قادر يجاوب (مش "مفيش استبيانات") --
    بنقولها صراحةً بدل ما نطمّن بالغلط.
    """
    try:
        from services.client_briefs_service import (
            list_new_briefs, mark_session_seen
        )
        from services.brief_reader import format_read
        set_chat_id(message.chat.id)
        briefs = list_new_briefs()

        if briefs is None:
            bot.reply_to(message, "⚠️ مش قادر أقرا من Supabase دلوقتي — جرب تاني.")
            return
        if not briefs:
            bot.reply_to(message, "📭 مفيش استبيانات جديدة.")
            return

        finals = [b for b in briefs if b.get("is_final")]
        partials = [b for b in briefs if not b.get("is_final")]
        bot.reply_to(message, f"📋 {len(finals)} استبيان مكتمل و{len(partials)} واقف في النص:")

        for brief in briefs:
            # القراءة التصميمية بدل السرد الخام -- الإجابات كاملة على
            # bahr-designs-office.web.app/briefs.html
            bot.send_message(message.chat.id, format_read(brief))
            mark_session_seen(brief.get("session_id"))

    except Exception as e:
        logger.error(f"❌ خطأ في /briefs: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['signature'])
def show_signature_command(message):
    """عرض سجل التوقيع — المؤكد والمقترح."""
    try:
        from services.signature import format_signature
        set_chat_id(message.chat.id)
        bot.reply_to(message, format_signature())
    except Exception as e:
        logger.error(f"❌ خطأ في /signature: {e}")
        send_error_message(message, str(e))

# ============================================================
# ⏰ أوامر التذكيرات
# ============================================================

@bot.message_handler(commands=['remind'])
def remind_command(message):
    """إضافة تذكير صريح: /remind 5m صلي أو /remind 19:00 اتصل بعصام"""
    try:
        set_chat_id(message.chat.id)
        text = message.text.replace('/remind', '', 1).strip()
        parts = text.split(maxsplit=1)
        
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ الصيغة غلط.\n\nأمثلة:\n/remind 5m صلي\n/remind 2h اتصل بعصام\n/remind 19:00 كلم عصام"
            )
            return
        
        time_part, reminder_text = parts[0], parts[1]
        send_at = parse_time_input(time_part)
        
        if not send_at:
            bot.reply_to(message, "❌ ما فهمتش الوقت.\n\nاستخدم:\n• 5m (دقايق)\n• 2h (ساعات)\n• 19:00 (وقت محدد)")
            return
        
        add_reminder(reminder_text, send_at, message.chat.id)
        bot.reply_to(message, f"✅ تمام! هفكرك في {send_at.strftime('%Y-%m-%d %H:%M')}\n\n📌 {reminder_text}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /remind: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['remind_time'])
def remind_time_command(message):
    """تغيير وقت التذكير الصباحي"""
    try:
        time_text = message.text.replace('/remind_time', '', 1).strip()
        
        if not time_text:
            bot.reply_to(message, f"⏰ معاد التذكير الحالي: {get_reminder_time()}\n\nلتغييره: /remind_time 08:30")
            return
        
        # تحقق من صحة الصيغة HH:MM
        if not re.fullmatch(r"\d{1,2}:\d{2}", time_text):
            bot.reply_to(message, "❌ الصيغة غلط. استخدم HH:MM\n\nمثال: /remind_time 08:30")
            return
        
        set_reminder_time(time_text)
        bot.reply_to(message, f"✅ تم تغيير معاد التذكير الصباحي لـ {time_text}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /remind_time: {e}")
        send_error_message(message, str(e))

# ============================================================
# 📅 أوامر الجدولة المتقدمة (APScheduler)
# ============================================================

@bot.message_handler(commands=['remind_daily'])
def remind_daily_command(message):
    """تذكير يومي: /remind_daily 10:00 نص التذكير"""
    try:
        from services import scheduler_service
        set_chat_id(message.chat.id)
        text = message.text.replace('/remind_daily', '', 1).strip()
        parts = text.split(maxsplit=1)
        
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ الصيغة غلط.\n\nمثال:\n/remind_daily 10:00 تفقد المشاريع\n/remind_daily 22:30 استرخي شوية"
            )
            return
        
        time_text, reminder_text = parts[0], parts[1]
        
        # تحليل الساعة والدقيقة
        try:
            time_parts = time_text.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("ساعة أو دقيقة غلط")
        except (ValueError, IndexError):
            bot.reply_to(message, "❌ الصيغة غلط. استخدم HH:MM\n\nمثال: /remind_daily 10:00 النص")
            return
        
        job_id = scheduler_service.add_daily_reminder(reminder_text, hour, minute, message.chat.id)
        
        if job_id:
            bot.reply_to(message, f"✅ تم إضافة التذكير اليومي!\n\n⏰ كل يوم الساعة {hour:02d}:{minute:02d}\n📌 {reminder_text}")
        else:
            send_error_message(message, "فشل عمل التذكير")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /remind_daily: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['remind_hourly'])
def remind_hourly_command(message):
    """تذكير كل ساعة: /remind_hourly 15 نص التذكير"""
    try:
        from services import scheduler_service
        set_chat_id(message.chat.id)
        text = message.text.replace('/remind_hourly', '', 1).strip()
        parts = text.split(maxsplit=1)
        
        if len(parts) < 1:
            bot.reply_to(
                message,
                "❌ الصيغة غلط.\n\nمثال:\n/remind_hourly 15 خذ شوية ماء\n/remind_hourly 0 تفقد الرسائل"
            )
            return
        
        try:
            minute = int(parts[0])
            reminder_text = parts[1] if len(parts) > 1 else "تذكير"
            
            if not (0 <= minute <= 59):
                raise ValueError()
        except ValueError:
            bot.reply_to(message, "❌ اكتب رقم الدقيقة (0-59)\n\nمثال: /remind_hourly 15 النص")
            return
        
        job_id = scheduler_service.add_hourly_reminder(reminder_text, minute, message.chat.id)
        
        if job_id:
            bot.reply_to(message, f"✅ تم إضافة التذكير بكل ساعة!\n\n⏰ في الدقيقة {minute:02d} من كل ساعة\n📌 {reminder_text}")
        else:
            send_error_message(message, "فشل عمل التذكير")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /remind_hourly: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['remind_monthly'])
def remind_monthly_command(message):
    """تذكير شهري: /remind_monthly 15 19:30 نص التذكير"""
    try:
        from services import scheduler_service
        set_chat_id(message.chat.id)
        text = message.text.replace('/remind_monthly', '', 1).strip()
        parts = text.split(maxsplit=2)
        
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ الصيغة غلط.\n\nمثال:\n/remind_monthly 15 19:30 استرجع الأقساط\n/remind_monthly 1 09:00 بداية الشهر"
            )
            return
        
        try:
            day = int(parts[0])
            time_parts = parts[1].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            reminder_text = parts[2] if len(parts) > 2 else "تذكير شهري"
            
            if not (1 <= day <= 31):
                raise ValueError("اليوم لازم 1-31")
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("ساعة أو دقيقة غلط")
        except ValueError as ve:
            bot.reply_to(message, f"❌ {str(ve) or 'تحقق من الأرقام'}\n\nمثال: /remind_monthly 15 19:30 النص")
            return
        
        job_id = scheduler_service.add_day_of_month_reminder(reminder_text, day, hour, minute, message.chat.id)
        
        if job_id:
            bot.reply_to(message, f"✅ تم إضافة التذكير الشهري!\n\n📅 اليوم {day} الساعة {hour:02d}:{minute:02d}\n📌 {reminder_text}")
        else:
            send_error_message(message, "فشل عمل التذكير")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /remind_monthly: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['schedule_list'])
def schedule_list_command(message):
    """عرض كل التذكيرات المجدولة"""
    try:
        from services import scheduler_service
        set_chat_id(message.chat.id)
        jobs = scheduler_service.list_scheduled_jobs()
        
        if not jobs:
            bot.reply_to(message, "📭 مفيش تذكيرات مجدولة دلوقتي.")
            return
        
        lines = []
        for i, job in enumerate(jobs, 1):
            lines.append(
                f"{i}. {job['الاسم']}\n   🆔 {job['معرّف']}\n   ⏳ المرة القادمة: {job['المرة_القادمة']}"
            )
        
        bot.reply_to(message, "📅 التذكيرات المجدولة:\n\n" + "\n\n".join(lines))
        
    except Exception as e:
        logger.error(f"❌ خطأ في /schedule_list: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['schedule_remove'])
def schedule_remove_command(message):
    """حذف تذكير مجدول: /schedule_remove job-id"""
    try:
        from services import scheduler_service
        set_chat_id(message.chat.id)
        job_id = message.text.replace('/schedule_remove', '', 1).strip()
        
        if not job_id:
            bot.reply_to(message, "❌ اكتب معرّف التذكير.\n\nاستخدم /schedule_list الأول عشان تعرف الـ id")
            return
        
        ok = scheduler_service.remove_scheduled_job(job_id)
        
        if ok:
            bot.reply_to(message, f"✅ تم حذف التذكير {job_id}")
        else:
            send_error_message(message, f"فشل حذف التذكير {job_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /schedule_remove: {e}")
        send_error_message(message, str(e))

# ============================================================
# 🗺️ أوامر الجراف (خريطة بحر)
# ============================================================

@bot.message_handler(commands=['graph_list'])
def graph_list_command(message):
    """عرض كل عقد الجراف"""
    try:
        nodes = graph_list_nodes()
        
        if not nodes:
            bot.reply_to(message, "📭 مفيش عقد في الجراف دلوقتي.")
            return
        
        lines = [f"• {n['label']} — `{n['id']}` ({n['category']})" for n in nodes]
        bot.reply_to(message, "🗺️ عقد الجراف الحالية:\n\n" + "\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /graph_list: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['graph_add'])
def graph_add_command(message):
    """إضافة عقدة جديدة: /graph_add الاسم | النوع | حقيقة1، حقيقة2"""
    try:
        text = message.text.replace('/graph_add', '', 1).strip()
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ الصيغة غلط.\n\nمثال:\n/graph_add اسم العنصر | project | حقيقة أولى، حقيقة تانية\n\n"
                f"الأنواع المتاحة: {', '.join(VALID_CATEGORIES)}"
            )
            return
        
        label = parts[0]
        category = parts[1].lower()
        
        if category not in VALID_CATEGORIES:
            bot.reply_to(message, f"❌ النوع غلط. استخدم واحد من: {', '.join(VALID_CATEGORIES)}")
            return
        
        facts_raw = parts[2] if len(parts) > 2 else ""
        facts_list = [f.strip() for f in facts_raw.split('،') if f.strip()] or ["(لسه مفيش تفاصيل)"]
        
        node_id = make_node_id_from_label(label)
        ok, msg = graph_add_node(node_id, label, category, facts_list, links_list=["ahmed"])
        
        if ok:
            bot.reply_to(message, f"✅ اتضاف في الجراف!\n\n📌 {label} ({category})\n🆔 `{node_id}`", parse_mode="Markdown")
        else:
            send_error_message(message, msg)
        
    except Exception as e:
        logger.error(f"❌ خطأ في /graph_add: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['graph_edit'])
def graph_edit_command(message):
    """تعديل عقدة موجودة: /graph_edit node-id | معلومة جديدة"""
    try:
        text = message.text.replace('/graph_edit', '', 1).strip()
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ الصيغة غلط.\n\nمثال:\n/graph_edit node-id | معلومة جديدة\n\n"
                "استخدم /graph_list الأول عشان تعرف الـ id"
            )
            return
        
        node_id, new_fact = parts[0], parts[1]
        ok, msg = graph_edit_node(node_id, new_fact)
        
        bot.reply_to(message, f"✅ {msg}" if ok else f"❌ {msg}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في /graph_edit: {e}")
        send_error_message(message, str(e))

@bot.message_handler(commands=['graph_delete'])
def graph_delete_command(message):
    """حذف عقدة: /graph_delete node-id"""
    try:
        node_id = message.text.replace('/graph_delete', '', 1).strip()
        
        if not node_id:
            bot.reply_to(message, "❌ اكتب الـ id بتاع العنصر.\n\nمثال: /graph_delete node-id\n\nاستخدم /graph_list الأول.")
            return
        
        ok, msg = graph_delete_node(node_id)
        
        if ok:
            bot.reply_to(message, "🗑️ اتحذف من الجراف!")
        else:
            send_error_message(message, msg)
        
    except Exception as e:
        logger.error(f"❌ خطأ في /graph_delete: {e}")
        send_error_message(message, str(e))
