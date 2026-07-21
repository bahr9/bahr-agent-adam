# -*- coding: utf-8 -*-
"""
⏰ وظائف الوقت والـ Timezone
- الوقت الحالي بتوقيت القاهرة
- تحويل الأوقات
"""

from datetime import datetime, timedelta
import re

try:
    from zoneinfo import ZoneInfo
    CAIRO_TZ = ZoneInfo("Africa/Cairo")
except:
    CAIRO_TZ = None

from config import CAIRO_TIMEZONE

def now_cairo():
    """الوقت الحالي بتوقيت القاهرة"""
    if CAIRO_TZ:
        return datetime.now(CAIRO_TZ)
    return datetime.now()

def get_arabic_day_name(dt=None):
    """اسم اليوم بالعربي"""
    if dt is None:
        dt = now_cairo()
    
    arabic_days = {
        "Monday": "الإثنين",
        "Tuesday": "الثلاثاء",
        "Wednesday": "الأربعاء",
        "Thursday": "الخميس",
        "Friday": "الجمعة",
        "Saturday": "السبت",
        "Sunday": "الأحد"
    }
    return arabic_days.get(dt.strftime("%A"), dt.strftime("%A"))

def parse_time_input(time_text):
    """
    تحويل نص الوقت لـ datetime
    يدعم: 5m, 2h, 19:00
    """
    time_text = time_text.strip()
    now = now_cairo()
    
    # صيغة "5m" (دقايق)
    m = re.fullmatch(r"(\d+)\s*m", time_text, re.IGNORECASE)
    if m:
        minutes = int(m.group(1))
        return now + timedelta(minutes=minutes)
    
    # صيغة "2h" (ساعات)
    h = re.fullmatch(r"(\d+)\s*h", time_text, re.IGNORECASE)
    if h:
        hours = int(h.group(1))
        return now + timedelta(hours=hours)
    
    # صيغة "19:00" (وقت محدد)
    t = re.fullmatch(r"(\d{1,2}):(\d{2})", time_text)
    if t:
        hour, minute = int(t.group(1)), int(t.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
    
    return None

def format_time_for_telegram(dt):
    """تنسيق الوقت للتليجرام"""
    return dt.strftime('%H:%M')

def format_datetime_for_display(dt):
    """تنسيق التاريخ والوقت للعرض"""
    return dt.strftime('%Y-%m-%d %H:%M')
