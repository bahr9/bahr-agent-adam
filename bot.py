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
from utils.atomic_io import atomic_write_json
from config import TELEGRAM_TOKEN, DATA_FILE, CONFIG_FILE

# إنشاء البوت
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)
logger.info(f"✅ تم تهيئة البوت")

def safe_send_message(chat_id, text, max_retries=3, **kwargs):
    """يبعت رسالة مع retry تلقائي"""
    import time
    for attempt in range(max_retries):
        try:
            return bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 3
                logger.warning("send_message فشل محاولة " + str(attempt+1) + " - ننتظر " + str(wait) + "s")
                time.sleep(wait)
            else:
                logger.error("send_message فشل نهائياً: " + str(e))
    return None

# ملف الإعدادات
config = {"chat_id": None, "reminder_time": "08:00"}

def load_config():
    """تحميل الإعدادات — من الملف المحلي أو Firestore"""
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل الإعدادات: {e}")
    # لو chat_id مش موجود → اجبه من Firestore
    if not config.get("chat_id"):
        try:
            from services.firebase_service import firestore_db
            if firestore_db:
                doc = firestore_db.collection("system_flags").document("chat_id").get()
                if doc.exists:
                    config["chat_id"] = doc.to_dict().get("chat_id")
                    logger.info("✅ chat_id استُرد من Firestore")
        except Exception:
            pass

def save_config():
    """حفظ الإعدادات — كتابة atomic عشان مفيش thread يقرا الملف وهو فاضي"""
    atomic_write_json(CONFIG_FILE, config)

def get_chat_id():
    """جلب chat_id"""
    return config.get("chat_id")

def set_chat_id(chat_id):
    """حفظ chat_id — محلياً + Firestore backup"""
    config["chat_id"] = chat_id
    save_config()
    # Firestore backup عشان متضيعش بعد restart
    try:
        from services.firebase_service import firestore_db
        if firestore_db:
            firestore_db.collection("system_flags").document("chat_id").set(
                {"chat_id": chat_id, "updated_at": str(__import__("datetime").datetime.now())}
            )
    except Exception:
        pass  # مش هيكراش لو Firebase مش شغال

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

@bot.message_handler(commands=['help'])
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
