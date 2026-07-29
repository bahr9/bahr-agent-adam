# -*- coding: utf-8 -*-
"""
💾 Atomic JSON I/O
- كتابة ملف JSON بشكل atomic (temp file + os.replace) عشان أي thread
  بيقرا الملف في نفس اللحظة ميلقهوش فاضي/ناقص أثناء الكتابة.
"""

import json
import os
import tempfile

from utils.logger import logger


def atomic_write_json(path: str, data) -> bool:
    """
    كتابة JSON بشكل آمن: بيكتب في ملف مؤقت في نفس الفولدر، وبعدين
    os.replace() عليه فوق الملف الأصلي — العملية دي atomic على مستوى
    نظام التشغيل، فمفيش لحظة يبقى فيها الملف الأصلي فاضي أو نص مكتوب.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في الكتابة الآمنة للملف {path}: {e}")
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return False
