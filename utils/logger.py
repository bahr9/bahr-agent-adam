# -*- coding: utf-8 -*-
"""
📝 نظام Logging مركزي
- console و file logging
- encoding صحيح للعربي
"""

import logging
import sys
import io
from config import LOG_FILE

# إصلاح UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def setup_logger():
    """تهيئة نظام logging"""
    logger = logging.getLogger("bahr_agent")
    logger.setLevel(logging.INFO)
    
    # فورمات الـ logging
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
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
