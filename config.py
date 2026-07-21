# -*- coding: utf-8 -*-
"""
⚙️ إعدادات Bahr Agent
- تحميل المتغيرات من البيئة
- ثوابت التطبيق
- إعدادات Firestore collections
"""

import os
from dotenv import load_dotenv

# تحميل المتغيرات من .env
load_dotenv()

# ============================================================
# 🔑 المفاتيح السرية (من .env)
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")

# التحقق من المفاتيح الأساسية
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN مش موجود في .env")
if not ANTHROPIC_API_KEY:
    raise ValueError("❌ ANTHROPIC_API_KEY مش موجود في .env")

# ============================================================
# 🗂️ Firestore Collections
# ============================================================
CONVERSATIONS_COLLECTION = "conversations"
REMINDERS_COLLECTION = "reminders"
RECURRING_TASKS_COLLECTION = "recurring_tasks"
GRAPH_COLLECTION = "bahr_graph_nodes"
CLIENTS_COLLECTION = "clients"
OFFICE_TASKS_COLLECTION = "office_tasks"
SITE_PROJECTS_COLLECTION = "site_projects"
AIN_AL_KHABEER_COLLECTION = "ain_al_khabeer_logs"
MEMORY_COLLECTION = "user_memory"  # الذاكرة الدائمة (ملخص متراكم لكل مستخدم)
EXPENSES_COLLECTION = "expenses"  # متابعة المصاريف
LOANS_COLLECTION = "loans"  # متابعة الأقساط والقروض
HUMAN_MODEL_COLLECTION = "adam_human_model"  # Human Model لأحمد

# ============================================================
# 📋 الثوابت العامة
# ============================================================
VALID_CATEGORIES = ["project", "team", "task", "issue", "topic", "hub", "client", "site", "office"]
MAX_CONVERSATION_HISTORY = 50
CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20251001"  # للمهام السريعة: استخراج النوايا وتلخيص الذاكرة
THINKING_BUDGET_TOKENS = 5000

# ملفات البيانات المحلية
DATA_FILE = "second_brain.json"
CONFIG_FILE = "config.json"
LOG_FILE = "bahr_agent.log"

# ============================================================
# ⏰ إعدادات الجدولة
# ============================================================
MORNING_GREETING_TIME = (8, 0)  # الساعة 8:00 صباحاً
FOLLOWUP_CHECK_INTERVAL = 30  # كل 30 دقيقة
REMINDER_CHECK_INTERVAL = 30  # كل 30 ثانية

# ============================================================
# 🌍 الـ Timezone
# ============================================================
CAIRO_TIMEZONE = "Africa/Cairo"
