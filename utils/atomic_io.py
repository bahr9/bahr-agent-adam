# -*- coding: utf-8 -*-
"""
💾 Atomic JSON I/O
- كتابة ملف JSON بشكل atomic (temp file + os.replace) عشان أي thread
  بيقرا الملف في نفس اللحظة ميلقهوش فاضي/ناقص أثناء الكتابة.
"""

import json
import os
import tempfile
import time

from utils.logger import logger

# عدد محاولات إعادة os.replace() لو فشلت مؤقتًا. على Linux (بيئة الإنتاج
# الفعلية -- Heroku) الـ rename() atomic ومش بيفشل لمجرد إن قارئ تاني فاتح
# الملف. على Windows بس (مثلاً أثناء التطوير المحلي)، قفل الملفات الافتراضي
# أصرم -- os.replace() ممكن يرمي PermissionError مؤقتًا لو thread تاني فاتح
# نفس الملف للقراءة في نفس اللحظة بالظبط. إعادة المحاولة كافية لأن القفل
# ده لحظي جدًا (مدة قراءة ملف صغير).
REPLACE_RETRY_ATTEMPTS = 5
REPLACE_RETRY_DELAY_SECONDS = 0.05


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

        last_error = None
        for attempt in range(REPLACE_RETRY_ATTEMPTS):
            try:
                os.replace(tmp_path, path)
                return True
            except OSError as e:
                last_error = e
                if attempt < REPLACE_RETRY_ATTEMPTS - 1:
                    time.sleep(REPLACE_RETRY_DELAY_SECONDS)
        raise last_error

    except Exception as e:
        logger.error(f"❌ خطأ في الكتابة الآمنة للملف {path}: {e}")
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return False
