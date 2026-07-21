# -*- coding: utf-8 -*-
"""
🌤️ ADAM Weather Service
=====================================================
بيجيب الطقس من wttr.in — مجاني بدون API key.

المواقع:
- مدينة العبور (البيت)
- 6 أكتوبر (موقع)
- التجمع الخامس (موقع)
"""

import requests
from utils.logger import logger

# ============================================================
# المواقع
# ============================================================

LOCATIONS = {
    "البيت": {
        "name": "مدينة العبور",
        "query": "Obour+City,Egypt",
        "emoji": "🏠"
    },
    "6_اكتوبر": {
        "name": "6 أكتوبر",
        "query": "6th+of+October+City,Egypt",
        "emoji": "🏗️"
    },
    "التجمع": {
        "name": "التجمع الخامس",
        "query": "New+Cairo,Egypt",
        "emoji": "🏗️"
    }
}


def get_weather(location_key: str = "البيت") -> dict:
    """
    جلب الطقس لموقع معين.
    
    Returns:
        {
            "location": str,
            "temp": str,
            "feels_like": str,
            "condition": str,
            "wind": str,
            "humidity": str,
            "alert": str or None
        }
    """
    location = LOCATIONS.get(location_key, LOCATIONS["البيت"])
    
    try:
        url = f"https://wttr.in/{location['query']}?format=j1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current = data["current_condition"][0]
        
        temp = current.get("temp_C", "")
        feels_like = current.get("FeelsLikeC", "")
        humidity = current.get("humidity", "")
        wind_speed = current.get("windspeedKmph", "")
        condition = current.get("weatherDesc", [{}])[0].get("value", "")
        
        # تحذيرات
        alert = None
        temp_val = int(temp) if temp else 0
        wind_val = int(wind_speed) if wind_speed else 0
        
        if temp_val >= 40:
            alert = f"🔴 حر شديد جداً ({temp}°C) — خطر على العمال في الموقع"
        elif temp_val >= 35:
            alert = f"🟡 حر عالي ({temp}°C) — خد بالك من العمال"
        
        if wind_val >= 40:
            alert = (alert or "") + f"\n💨 رياح قوية ({wind_speed} km/h) — احتياط في الموقع"
        
        return {
            "location": location["name"],
            "emoji": location["emoji"],
            "temp": f"{temp}°C",
            "feels_like": f"{feels_like}°C",
            "condition": condition,
            "wind": f"{wind_speed} km/h",
            "humidity": f"{humidity}%",
            "alert": alert
        }
    
    except Exception as e:
        logger.error(f"❌ Weather error for {location['name']}: {e}")
        return {
            "location": location["name"],
            "emoji": location["emoji"],
            "temp": "غير متاح",
            "feels_like": "",
            "condition": "",
            "wind": "",
            "humidity": "",
            "alert": None
        }


def get_all_weather() -> str:
    """جلب الطقس لكل المواقع وتنسيقه"""
    results = []
    
    for key in LOCATIONS:
        weather = get_weather(key)
        line = f"{weather['emoji']} {weather['location']}: {weather['temp']}"
        if weather['condition']:
            line += f" — {weather['condition']}"
        results.append(line)
        
        if weather.get('alert'):
            results.append(f"  {weather['alert']}")
    
    return "\n".join(results)


def get_weather_for_morning_brief() -> str:
    """
    ملخص الطقس للـ Morning Brief.
    بيرجع نص مختصر مع تحذيرات لو موجودة.
    """
    try:
        # نجيب طقس البيت كمرجع رئيسي
        home_weather = get_weather("البيت")
        site1_weather = get_weather("6_اكتوبر")
        site2_weather = get_weather("التجمع")
        
        summary = f"🌤️ الطقس النهارده:\n"
        summary += f"• البيت (العبور): {home_weather['temp']}"
        if home_weather['condition']:
            summary += f" — {home_weather['condition']}"
        summary += f"\n• 6 أكتوبر: {site1_weather['temp']}"
        summary += f"\n• التجمع: {site2_weather['temp']}"
        
        # تحذيرات
        alerts = []
        for w in [home_weather, site1_weather, site2_weather]:
            if w.get('alert'):
                alerts.append(w['alert'])
        
        if alerts:
            summary += "\n\n" + "\n".join(set(alerts))
        
        return summary
    
    except Exception as e:
        logger.error(f"❌ Weather brief error: {e}")
        return ""
