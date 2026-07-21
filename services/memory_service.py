# -*- coding: utf-8 -*-
"""
🧠 خدمة الذاكرة الدائمة (Persistent Memory)
- ملخص متراكم عن المستخدم عبر كل الجلسات (مش بس آخر شوية رسائل)
- بيتحدّث تلقائيًا بعد كل رسالة عن طريق موديل خفيف وسريع
"""

from utils.logger import logger
from services.firebase_service import get_memory_summary, save_memory_summary
from services.claude_service import summarize_memory

def get_memory(user_id):
    """جلب ملخص الذاكرة الدائمة الحالي لمستخدم معيّن"""
    return get_memory_summary(user_id)

def update_memory(user_id, user_message, assistant_reply):
    """
    تحديث الذاكرة الدائمة بعد تبادل رسائل جديد.
    بتستدعي موديل خفيف يقرر هل فيه حاجة جديدة تستاهل تتحفظ أو لأ.
    """
    try:
        old_summary = get_memory(user_id)
        new_summary = summarize_memory(old_summary, user_message, assistant_reply)
        
        if new_summary and new_summary != old_summary:
            save_memory_summary(user_id, new_summary)
            logger.info(f"🧠 اتحدّثت الذاكرة الدائمة لـ {user_id}")
            
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث الذاكرة الدائمة: {e}")
