# -*- coding: utf-8 -*-
"""
🤖 تهيئة البوت الأساسية
- إنشاء البوت
- المعالجات الأساسية
"""

import telebot
import os
import json
from utils.logger import logger
from config import TELEGRAM_TOKEN, DATA_FILE, CONFIG_FILE

# إنشاء البوت
bot = telebot.TeleBot(TELEGRAM_TOKEN)
logger.info(f"✅ تم تهيئة البوت")

# ملف الإعدادات
config = {"chat_id": None, "reminder_time": "08:00"}

def load_config():
    """تحميل الإعدادات"""
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل الإعدادات: {e}")

def save_config():
    """حفظ الإعدادات"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الإعدادات: {e}")

def get_chat_id():
    """جلب chat_id"""
    return config.get("chat_id")

def set_chat_id(chat_id):
    """حفظ chat_id"""
    config["chat_id"] = chat_id
    save_config()

def get_reminder_time():
    """جلب وقت التذكير الصباحي"""
    return config.get("reminder_time", "08:00")

def set_reminder_time(time_str):
    """تعيين وقت التذكير الصباحي"""
    config["reminder_time"] = time_str
    save_config()

# ============================================================
# 🎹 Keyboard Menu
# ============================================================

def get_main_keyboard():
    """الكيبورد الرئيسي"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        telebot.types.KeyboardButton("💰 المصاريف والأقساط"),
        telebot.types.KeyboardButton("🏗️ المشاريع"),
        telebot.types.KeyboardButton("🔔 التذكيرات"),
        telebot.types.KeyboardButton("🧠 الذاكرة والجراف"),
        telebot.types.KeyboardButton("👁️ عين الخبير"),
        telebot.types.KeyboardButton("🌤️ الطقس")
    )
    return keyboard

def get_expenses_keyboard():
    """كيبورد المصاريف"""
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📊 ملخص المصاريف", callback_data="expenses_summary"),
        telebot.types.InlineKeyboardButton("➕ صرفت فلوس", callback_data="expenses_add"),
        telebot.types.InlineKeyboardButton("📅 الأقساط الشهر ده", callback_data="loans_month"),
        telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return keyboard

def get_projects_keyboard():
    """كيبورد المشاريع"""
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📋 حالة المشاريع", callback_data="projects_status"),
        telebot.types.InlineKeyboardButton("📅 المواعيد الجاية", callback_data="projects_deadlines"),
        telebot.types.InlineKeyboardButton("⚠️ تنبيهات المشاريع المتأخرة", callback_data="projects_alerts"),
        telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return keyboard

def get_reminders_keyboard():
    """كيبورد التذكيرات"""
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📋 تذكيرات حالية", callback_data="reminders_list"),
        telebot.types.InlineKeyboardButton("⏰ ذكرني بعد كذا", callback_data="reminders_new"),
        telebot.types.InlineKeyboardButton("🔁 تذكير متكرر", callback_data="reminders_recurring"),
        telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return keyboard

def get_memory_keyboard():
    """كيبورد الذاكرة"""
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📝 آخر الملاحظات", callback_data="memory_notes"),
        telebot.types.InlineKeyboardButton("🗺️ عناصر خريطة بحر", callback_data="memory_graph"),
        telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return keyboard

def get_eye_expert_keyboard():
    """كيبورد عين الخبير"""
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton("👁️ آخر أسئلة العملاء", callback_data="eye_expert_logs"),
        telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return keyboard

# ============================================================
# 📋 الأوامر الأساسية
# ============================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """أمر البدء"""
    try:
        set_chat_id(message.chat.id)
        
        welcome_text = f"""🌊 مرحباً بك يا أحمد!

أنا Bahr Agent — دماغك الثاني! 🧠

📌 الأوامر المتاحة:
/save مهمتي → حفظ مهمة
/tasks → عرض المهام
/done رقم → إنجاز مهمة
/ideas → عرض الأفكار
/clear → مسح المهام

/remind 5m صلي → ذكرني بعد 5 دقايق
/remind 19:00 اتصل → ذكرني الساعة 7 مساءً
/remind_time 08:00 → تغيير وقت التذكير الصباحي

🗺️ أوامر الجراف:
/graph_list → عرض العناصر
/graph_add اسم | نوع | حقيقة → إضافة عنصر
/graph_edit id | معلومة → تعديل عنصر
/graph_delete id → حذف عنصر

💬 أو فقط اكتب "ذكرني بعد ٥ دقايق" وهفهمك!"""
        
        bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())
        logger.info(f"✅ مستخدم جديد: {message.from_user.first_name} (ID: {message.chat.id})")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر البدء: {e}")
        try:
            bot.reply_to(message, f"❌ حصلت مشكلة: {str(e)}")
        except:
            pass

# ============================================================
# 🛡️ معالج الأخطاء العام
# ============================================================

def send_error_message(message, error_text):
    """إرسال رسالة خطأ آمنة"""
    try:
        bot.reply_to(message, f"❌ {error_text}")
    except Exception as e:
        logger.error(f"❌ فشل إرسال رسالة الخطأ: {e}")

# تحميل الإعدادات عند البدء
load_config()
