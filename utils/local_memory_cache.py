# -*- coding: utf-8 -*-
"""
🧠 Local fallback cache للمحادثات والذاكرة الدائمة
- الهدف الوحيد: لو قراءة Firestore فشلت (quota exhaustion غالبًا)، آدم يرجع
  لآخر نسخة معروفة محليًا بدل ما يتصرف كإنه مفيش تاريخ خالص ("إنسان جديد").
- نفس نمط second_brain.json في reminder_service.py -- ملف محلي يتحمّل في
  الذاكرة عند الاستيراد، وبيتحدّث (write-through) بعد كل قراءة Firestore ناجحة.
- ده مش بديل لـ Firestore -- مجرد شبكة أمان لحظة فشل القراءة الفعلية.
"""

import os
from utils.logger import logger
from utils.atomic_io import atomic_write_json
from config import MEMORY_CACHE_FILE

_cache = {"conversations": {}, "memory_summaries": {}}


def _load_cache():
    global _cache
    if os.path.exists(MEMORY_CACHE_FILE):
        try:
            import json
            with open(MEMORY_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _cache = {
                    "conversations": data.get("conversations", {}),
                    "memory_summaries": data.get("memory_summaries", {}),
                }
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل memory_cache المحلي: {e}")
            _cache = {"conversations": {}, "memory_summaries": {}}


_load_cache()


def _save_cache():
    atomic_write_json(MEMORY_CACHE_FILE, _cache)


def update_conversation_cache(user_id, messages):
    _cache["conversations"][str(user_id)] = messages
    _save_cache()


def get_cached_conversation(user_id):
    return _cache["conversations"].get(str(user_id), [])


def update_memory_cache(user_id, summary):
    _cache["memory_summaries"][str(user_id)] = summary
    _save_cache()


def get_cached_memory_summary(user_id):
    return _cache["memory_summaries"].get(str(user_id), "")
