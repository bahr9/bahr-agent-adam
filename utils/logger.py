# -*- coding: utf-8 -*-
"""
📝 نظام Logging مركزي
- console و file logging
- encoding صحيح للعربي
"""

import logging
import os
import sys
import io
from config import LOG_FILE

# إصلاح UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def detect_environment():
    """[prod] / [local] / [test] -- علامة بيئة في كل سطر.

    السبب مش تنظيمي، ده عطل تشخيصي حقيقي حصل مرتين في يوم واحد
    (2026-08-08): تشغيلات الاختبارات بتكتب في **نفس** الملف اللي بيتقرا
    لتشخيص الإنتاج، ومن غير علامة الاتنين شكلهم واحد. النتيجة: 347 إنذار
    اختبار اتقروا على إنهم خراب بيانات مالية حقيقي، و114 رفض محلي اتقروا
    على إنهم قطع اتصال بين الأنظمة. الاتنين كانوا كذب، والاتنين كانوا
    هيتمنعوا بكلمة واحدة في أول السطر.

    الترتيب مقصود: الاختبار بيغلب الكل (تشغيلة اختبار جوه بيئة الإنتاج
    تفضل اختبار)، وبعدين الإنتاج، وبعدين المحلي كافتراضي آمن.
    """
    argv0 = os.path.basename(sys.argv[0] or "")
    if argv0.startswith("test_") or "pytest" in argv0 or "PYTEST_CURRENT_TEST" in os.environ:
        return "test"
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"):
        return "prod"
    return "local"


ENVIRONMENT = detect_environment()


def setup_logger():
    """تهيئة نظام logging"""
    logger = logging.getLogger("bahr_agent")
    logger.setLevel(logging.INFO)

    # فورمات الـ logging -- علامة البيئة جنب المستوى عشان أي grep على
    # اللوج يقدر يفصل الإنتاج عن الاختبارات من غير تخمين.
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [' + ENVIRONMENT + '] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()
