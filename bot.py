# -*- coding: utf-8 -*-
"""
🤖 تهيئة البوت الأساسية
- إنشاء البوت
- المعالجات الأساسية
"""

import telebot
import os
import json
import time
import threading
from utils.logger import logger
from config import TELEGRAM_TOKEN, DATA_FILE, CONFIG_FILE

# إنشاء البوت
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)
logger.info(f"✅ تم تهيئة البوت")

# ============================================================
# Retry — إرسال رسالة مع إعادة المحاولة
# ============================================================

def safe_send_message(chat_id, text, max_retries=3, **kwargs):
    """
    يبعت رسالة مع retry تلقائي لو فشلت
    بيجرب 3 مرات مع انتظار متزايد بينهم
    """
    for attempt in range(max_retries):
        try:
            return bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            err = str(e)
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 3
                logger.warning(f"⚠️ send_message فشل (محاولة {attempt+1}/{max_retries}): {err} — ننتظر {wait}s")
                time.sleep(wait)
            else:
                logger.error(f"❌ send_message فشل نهائياً بعد {max_retries} محاولات: {err}")
    return None

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
        
        bot.reply_to(message, welcome_text)
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
