# -*- coding: utf-8 -*-
"""
🧾 Runtime Capabilities Registry -- Runtime Capabilities & Tool Health V1
=====================================================
سجل بنيوي واحد لكل الأدوات المتاحة فعليًا لآدم دلوقتي. هذا الملف بنية تحتية
Runtime بس -- مش بداية لـ Agent Contracts أوسع، ومفيش أي إعادة تصميم لعقد
أي أداة موجودة.

**قاعدة منع الانحراف (drift) -- الأهم في الملف ده كله:**
قايمة أسماء الأدوات (`tool_name`) بتتشتق **حصريًا وبرمجيًا** من
`services.claude_service.TOOLS` -- المصدر الحقيقي الوحيد. الملف ده **مايعرّفش**
قايمة تانية من الأدوات، ومايخترعش أي capability مش موجودة فعليًا هناك.

لكل أداة، فيه بيانات وصفية إضافية (domain, operation_type, criticality,
health_check_supported, safe_probe, timeout_ms, source_owner) -- دي بيانات
محتاجة حكم بشري (مينفعش تُشتق آليًا بأمان، خصوصًا "هل الأداة دي آمنة تُستدعى
بدون أي جانب-تأثير؟")، فهي مُعرّفة يدويًا هنا في `_TOOL_METADATA`. **أي أداة
حقيقية في TOOLS لكن مالهاش entry هنا بتاخد entry افتراضي محافظ** (unclassified/
NOT_MONITORED) تلقائيًا -- صفر أداة بتختفي من الـ Registry بصمت، وصفر أداة
بتتصنّف "آمنة" افتراضيًا من غير قرار صريح.

اختبار الانحراف (`test_tool_health.py`) بيتأكد إن:
  1. كل tool_name في _TOOL_METADATA موجود فعليًا في claude_service.TOOLS
     الحالية (يمسك entries قديمة/متروكة لو أداة اتشالت).
  2. كل tool_name في claude_service.TOOLS ليه entry في الـ Registry
     (مضمونة بالتصميم عبر الـ default-fill، لكن بيتفحص صراحة برضه).
"""

from services.claude_service import TOOLS

DEFAULT_TIMEOUT_MS = 5000

# ============================================================
# Safe Probes -- استدعاء مباشر للدالة الحقيقية اللي بتنفّذ الأداة، من غير
# ما يمر على الموديل أو على _execute_tool. صفر جانب-تأثير (read-only بحت،
# صفر باراميتر إجباري). أي استيراد جوه الدالة نفسها -- مفيش استيراد ثقيل
# على مستوى الملف عشان نتجنب أي احتمال دائرية.
# ============================================================

def _probe_list_graph_nodes():
    from services.firebase_service import graph_list_nodes
    return graph_list_nodes()


def _probe_list_expenses():
    from services.firebase_service import get_expenses
    return get_expenses(limit=5)


def _probe_expense_summary():
    from services.firebase_service import get_expense_summary
    return get_expense_summary()


def _probe_loan_overview():
    from services import loan_service
    return loan_service.get_overview()


def _probe_list_reminders():
    from services.firebase_service import list_all_reminders
    return list_all_reminders()


def _probe_get_human_model():
    from services.firebase_service import get_human_model
    return get_human_model()


def _probe_get_bahr_projects():
    from services.firebase_service import get_bahr_projects
    return get_bahr_projects()


def _probe_get_bahr_sites():
    from services.firebase_service import get_bahr_sites
    return get_bahr_sites()


def _probe_list_recurring_reminders():
    from services.recurring_reminders_service import get_active_recurring_reminders
    return get_active_recurring_reminders()


def _probe_get_self_diagnosis_report():
    from services import self_diagnosis
    return {
        "fallback": self_diagnosis.compute_fallback_count(),
        "rejection": self_diagnosis.compute_validator_rejection_diagnosis(),
        "mismatch": self_diagnosis.compute_verbatim_mismatch_diagnosis(),
    }


def _probe_get_adam_self_state():
    from services import self_state_core
    return self_state_core.compute_self_state_core()


def _probe_loan_month_installments():
    from services import loan_service
    return loan_service.get_month_installments(loan_service.get_current_month_key())


def _probe_get_graph_node_details():
    from services.firebase_service import graph_get_node
    return graph_get_node("health_probe_nonexistent_id")


def _probe_get_weather():
    from weather_service import get_all_weather
    return get_all_weather()


def _probe_get_upcoming_deadlines():
    from services.firebase_service import get_upcoming_deadlines
    from bot import get_chat_id
    return get_upcoming_deadlines(get_chat_id(), 30)


def _probe_search_memory_notes():
    from services.firebase_service import search_memory_notes
    from bot import get_chat_id
    return search_memory_notes(get_chat_id(), "", limit=3)


def _probe_list_memory_notes():
    from services.firebase_service import list_memory_notes
    from bot import get_chat_id
    return list_memory_notes(get_chat_id(), limit=3)


def _probe_get_project_details():
    from services.firebase_service import get_project_details
    return get_project_details("health_probe_nonexistent_id")


def _probe_get_client_followups():
    from services.firebase_service import firestore_db
    return list(firestore_db.collection("client_followups").limit(3).stream())


def _probe_get_upcoming_followups():
    from services.firebase_service import firestore_db
    return list(firestore_db.collection("client_followups").limit(3).stream())


def _probe_get_eye_expert_prompt():
    from services.firebase_service import firestore_db
    return firestore_db.collection("eye_expert_config").document("system_prompt").get()


def _probe_get_eye_expert_logs():
    from services.firebase_service import get_ain_al_khabeer_logs
    return get_ain_al_khabeer_logs(limit=3)


def _probe_list_decisions():
    from services.firebase_service import get_decisions
    return get_decisions(limit=3)


def _probe_get_agent_task_status():
    from services import agent_orchestration
    return agent_orchestration.get_agent_task_status("health_probe_nonexistent_id")


# ============================================================
# البيانات الوصفية -- يدوي، مبني على قراءة فعلية لكل tool_name وdispatch
# branch في services/claude_service.py (مش تخمين). operation_type من
# {"read","write","delete","analysis","system"}.
# ============================================================

_TOOL_METADATA = {
    "list_graph_nodes":            {"domain": "graph", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_list_graph_nodes,
                                     "source_owner": "services/firebase_service.py"},
    "add_graph_node":              {"domain": "graph", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "edit_graph_node":              {"domain": "graph", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "delete_graph_node":           {"domain": "graph", "operation_type": "delete", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "create_reminder":             {"domain": "reminders", "operation_type": "write", "criticality": "low", "source_owner": "services/reminder_service.py"},
    "add_expense":                 {"domain": "expenses", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "list_expenses":                {"domain": "expenses", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_list_expenses,
                                     "source_owner": "services/firebase_service.py"},
    "expense_summary":              {"domain": "expenses", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_expense_summary,
                                     "source_owner": "services/firebase_service.py"},
    "loan_overview":                {"domain": "loans", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_loan_overview,
                                     "source_owner": "services/loan_service.py"},
    "loan_month_installments":      {"domain": "loans", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_loan_month_installments,
                                     "source_owner": "services/loan_service.py"},
    "loan_record_installment":     {"domain": "loans", "operation_type": "write", "criticality": "high", "source_owner": "services/loan_commands.py"},
    "loan_update_installment":     {"domain": "loans", "operation_type": "write", "criticality": "high", "source_owner": "services/loan_commands.py"},
    "loan_resolve_conflict":       {"domain": "loans", "operation_type": "write", "criticality": "high", "source_owner": "services/loan_commands.py"},
    "save_memory_note":            {"domain": "memory", "operation_type": "write", "criticality": "low", "source_owner": "services/firebase_service.py"},
    "get_graph_node_details":      {"domain": "graph", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_graph_node_details,
                                     "source_owner": "services/firebase_service.py"},
    "get_weather":                  {"domain": "external", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_weather,
                                     "source_owner": "weather_service.py"},
    "update_memory_note":          {"domain": "memory", "operation_type": "write", "criticality": "low", "source_owner": "services/firebase_service.py"},
    "get_upcoming_deadlines":       {"domain": "memory", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_upcoming_deadlines,
                                     "source_owner": "services/firebase_service.py"},
    "save_memory_note_with_deadline": {"domain": "memory", "operation_type": "write", "criticality": "low", "source_owner": "services/firebase_service.py"},
    "delete_memory_note":          {"domain": "memory", "operation_type": "delete", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "search_memory_notes":          {"domain": "memory", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_search_memory_notes,
                                     "source_owner": "services/firebase_service.py"},
    "list_memory_notes":            {"domain": "memory", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_list_memory_notes,
                                     "source_owner": "services/firebase_service.py"},
    "list_reminders":               {"domain": "reminders", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_list_reminders,
                                     "source_owner": "services/firebase_service.py"},
    "delete_reminder":             {"domain": "reminders", "operation_type": "delete", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "delete_all_reminders":        {"domain": "reminders", "operation_type": "delete", "criticality": "high", "source_owner": "services/firebase_service.py"},
    "get_human_model":              {"domain": "human_model", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_human_model,
                                     "source_owner": "services/firebase_service.py"},
    "update_human_model":          {"domain": "human_model", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "get_bahr_projects":            {"domain": "projects", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_bahr_projects,
                                     "source_owner": "services/firebase_service.py"},
    "get_bahr_sites":                {"domain": "projects", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_bahr_sites,
                                     "source_owner": "services/firebase_service.py"},
    "get_project_details":          {"domain": "projects", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_project_details,
                                     "source_owner": "services/firebase_service.py"},
    "create_recurring_reminder":   {"domain": "reminders", "operation_type": "write", "criticality": "low", "source_owner": "services/firebase_service.py"},
    "list_recurring_reminders":     {"domain": "reminders", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_list_recurring_reminders,
                                     "source_owner": "services/firebase_service.py"},
    "delete_recurring_reminder":   {"domain": "reminders", "operation_type": "delete", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "get_backup_status":            {"domain": "system", "operation_type": "system", "criticality": "low", "source_owner": "services/claude_service.py (GitHub API)"},
    "get_self_diagnosis_report":    {"domain": "system_health", "operation_type": "analysis", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_self_diagnosis_report,
                                     "source_owner": "services/self_diagnosis.py"},
    "get_adam_self_state":          {"domain": "system_health", "operation_type": "analysis", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_adam_self_state,
                                     "source_owner": "services/self_state_core.py"},
    "add_client_followup":         {"domain": "clients", "operation_type": "write", "criticality": "medium", "source_owner": "services/claude_service.py (raw Firestore)"},
    "update_client_followup":      {"domain": "clients", "operation_type": "write", "criticality": "medium", "source_owner": "services/claude_service.py (raw Firestore)"},
    "get_client_followups":         {"domain": "clients", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_client_followups,
                                     "source_owner": "services/claude_service.py (raw Firestore)"},
    "get_upcoming_followups":       {"domain": "clients", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_upcoming_followups,
                                     "source_owner": "services/claude_service.py (raw Firestore)"},
    "create_project":               {"domain": "projects", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "update_project_details":      {"domain": "projects", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "delete_project":               {"domain": "projects", "operation_type": "delete", "criticality": "high", "source_owner": "services/firebase_service.py"},
    "add_site":                     {"domain": "projects", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "delete_expense":               {"domain": "expenses", "operation_type": "delete", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "update_project_status":       {"domain": "projects", "operation_type": "write", "criticality": "medium", "source_owner": "services/claude_service.py (raw Firestore)"},
    "get_eye_expert_prompt":        {"domain": "eye_expert", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_eye_expert_prompt,
                                     "source_owner": "services/firebase_service.py"},
    "update_eye_expert_prompt":    {"domain": "eye_expert", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "get_eye_expert_logs":          {"domain": "eye_expert", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_eye_expert_logs,
                                     "source_owner": "services/firebase_service.py"},
    "request_verified_expression": {"domain": "system_health", "operation_type": "analysis", "criticality": "high", "source_owner": "services/verified_expression.py"},
    "web_search":                   {"domain": "external", "operation_type": "analysis", "criticality": "low",
                                     "runtime_handler": "anthropic_native_tool", "source_owner": "Anthropic (server-side tool)"},
    "save_decision":                {"domain": "decisions", "operation_type": "write", "criticality": "medium", "source_owner": "services/firebase_service.py"},
    "list_decisions":               {"domain": "decisions", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_list_decisions,
                                     "source_owner": "services/firebase_service.py"},
    "dispatch_agent_task":          {"domain": "agent_orchestration", "operation_type": "write", "criticality": "medium", "source_owner": "services/agent_orchestration.py"},
    "get_agent_task_status":        {"domain": "agent_orchestration", "operation_type": "read", "criticality": "low",
                                     "health_check_supported": True, "safe_probe": _probe_get_agent_task_status,
                                     "source_owner": "services/agent_orchestration.py"},
    # عمدًا صفر health_check_supported هنا -- منع أي حلقة مراقبة ذاتية
    # (تقرير صحة الأدوات مايراقبش نفسه عبر heartbeat).
    "get_tools_health_status":      {"domain": "system_health", "operation_type": "analysis", "criticality": "low",
                                     "source_owner": "services/tool_health_engine.py"},
}


def _default_entry(tool_name: str) -> dict:
    """
    Entry افتراضي محافظ لأي tool_name موجود فعليًا في TOOLS لكن مفيش له
    تصنيف يدوي هنا (أداة جديدة اتضافت بعد آخر مراجعة للـ Registry، مثلًا).
    صفر health_check_supported، صفر safe_probe -- NOT_MONITORED افتراضيًا،
    مش "healthy" بالتخمين.
    """
    return {
        "domain": "unclassified",
        "operation_type": "system",
        "criticality": "unknown",
        "health_check_supported": False,
        "safe_probe": None,
        "runtime_handler": "claude_service._execute_tool",
        "timeout_ms": DEFAULT_TIMEOUT_MS,
        "source_owner": "unclassified -- needs manual registry review",
    }


def build_registry() -> dict:
    """
    الـ Registry الفعلي -- dict مفتاحه tool_name. تُشتق قايمة الأسماء
    حصريًا من claude_service.TOOLS الحقيقية (صفر اختراع، صفر قايمة موازية).
    """
    registry = {}
    for tool in TOOLS:
        name = tool["name"]
        meta = dict(_TOOL_METADATA.get(name, _default_entry(name)))
        meta.setdefault("availability", True)
        meta.setdefault("health_check_supported", False)
        meta.setdefault("safe_probe", None)
        meta.setdefault("runtime_handler", "claude_service._execute_tool")
        meta.setdefault("timeout_ms", DEFAULT_TIMEOUT_MS)
        meta.setdefault("criticality", "unknown")
        meta["tool_name"] = name
        registry[name] = meta
    return registry


def get_registry() -> dict:
    """نقطة الدخول العامة -- تُعاد حسابها كل مرة (صفر تخزين، صفر cache قديم ممكن ينحرف)."""
    return build_registry()


def check_drift() -> dict:
    """
    فحص الانحراف الصريح -- يرجع:
      missing_from_metadata: أدوات حقيقية في TOOLS بدون تصنيف يدوي (بتاخد
        default محافظ، مش خطأ، لكن يستاهل مراجعة).
      stale_in_metadata: مفاتيح في _TOOL_METADATA مش موجودة في TOOLS الحقيقية
        (أداة اتشالت من TOOLS بس نسينا نشيلها من هنا -- تنظيف مطلوب).
    """
    real_names = {tool["name"] for tool in TOOLS}
    metadata_names = set(_TOOL_METADATA.keys())
    return {
        "missing_from_metadata": sorted(real_names - metadata_names),
        "stale_in_metadata": sorted(metadata_names - real_names),
    }


def get_safe_probe_tools() -> list:
    """أسماء كل الأدوات اللي عندها safe_probe فعلي (health_check_supported=True)."""
    registry = get_registry()
    return [name for name, meta in registry.items() if meta.get("health_check_supported") and meta.get("safe_probe")]
