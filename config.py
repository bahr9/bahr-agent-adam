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
SUPABASE_URL = os.getenv("SUPABASE_URL")  # Pilot: Firestore -> Supabase migration (recurring reminders)
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # service_role key

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
PROJECT_FILES_COLLECTION = "project_files"
PRICE_BASE_COLLECTION = "price_base"  # ملفات مشاريع التصميم (الفجوة 1، 2026-08-04)
MEMORY_COLLECTION = "user_memory"  # الذاكرة الدائمة (ملخص متراكم لكل مستخدم)
EXPENSES_COLLECTION = "expenses"  # متابعة المصاريف
LOANS_COLLECTION = "loans"  # متابعة الأقساط والقروض
DECISION_LEDGER_COLLECTION = "decision_ledger"  # سجل القرارات المعتمدة
HUMAN_MODEL_COLLECTION = "adam_human_model"  # Human Model لأحمد
EVENTS_COLLECTION = "adam_events"  # Event Store -- سجل الأحداث الثابت (ADAM Self-State & Observation System)
SELF_STATE_COLLECTION = "adam_self_state"  # State History محدودة -- آخر مستوى Active اتبلّغ بيه لكل بُعد (Stage 5)
STATE_SNAPSHOTS_COLLECTION = "adam_state_snapshots"  # لقطات Self-State وقت التعبير الفعلي بس (Stage 6/7 -- Evidence Trace)
EXPRESSIONS_COLLECTION = "adam_expressions"  # سجل كل تعبير اتبعت لأحمد + رابطه بالـ state/evidence (Stage 6/7)
TOOL_HEALTH_CHECKS_COLLECTION = "tool_health_checks"  # نتائج الـ heartbeat الآمن (Runtime Capabilities & Tool Health V1)
TOOL_FAILURES_LOG_COLLECTION = "tool_failures_log"  # فشل حقيقي أثناء تنفيذ فعلي من مستخدم (نفس المرحلة)
TOOL_HEALTH_ALERT_STATE_COLLECTION = "tool_health_alert_state"  # آخر حالة تنبيه لكل أداة -- لمنع التكرار (dedup/cooldown)
PERSONAL_TASKS_COLLECTION = "personal_tasks"  # مهام /save السريعة (مختلفة عن office_tasks)
IDEAS_COLLECTION = "ideas"  # أفكار عابرة
PROJECT_STATUS_ALERT_STATE_COLLECTION = "project_status_alert_state"  # آخر حالة اتبلّغ بيها لكل مشروع Bahr OS (dedup/cooldown)
AGENT_TASKS_COLLECTION = "agent_tasks"  # طابور مهام آدم -> Hope/مداد/عين الخبير (Orchestration Phase 1)

# ============================================================
# 🐘 Supabase (Pilot -- Firestore migration, recurring reminders only)
# ============================================================
RECURRING_REMINDERS_TABLE = "recurring_reminders"  # اسم الجدول في Supabase

# ============================================================
# 📋 الثوابت العامة
# ============================================================
VALID_CATEGORIES = ["project", "team", "task", "issue", "topic", "hub", "client", "site", "office"]
MAX_CONVERSATION_HISTORY = 50  # كام تبادل نجيب من Firestore
CONVERSATION_CONTEXT_WINDOW = 30  # كام تبادل فعليًا يتبعت لكلود كـ context (كان 15/8 قيم متفرقة)
CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20251001"  # للمهام السريعة: استخراج النوايا وتلخيص الذاكرة
THINKING_BUDGET_TOKENS = 5000

# ملفات البيانات المحلية
DATA_FILE = "second_brain.json"
CONFIG_FILE = "config.json"
LOG_FILE = "bahr_agent.log"
MEMORY_CACHE_FILE = "memory_cache.json"  # fallback محلي للمحادثات/الذاكرة الدائمة لو قراءة Firestore فشلت

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
