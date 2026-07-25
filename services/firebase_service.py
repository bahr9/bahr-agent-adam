# -*- coding: utf-8 -*-
"""
🔥 خدمة Firebase/Firestore
- الاتصال والعمليات الأساسية
- CRUD operations منظمة
"""

import json
import firebase_admin
from firebase_admin import credentials, firestore
from utils.logger import logger
from config import (
    FIREBASE_CREDENTIALS_JSON,
    GRAPH_COLLECTION,
    HUMAN_MODEL_COLLECTION,
    CONVERSATIONS_COLLECTION,
    REMINDERS_COLLECTION,
    CLIENTS_COLLECTION,
    OFFICE_TASKS_COLLECTION,
    SITE_PROJECTS_COLLECTION,
    AIN_AL_KHABEER_COLLECTION,
    MEMORY_COLLECTION,
    EXPENSES_COLLECTION,
    LOANS_COLLECTION
)
import time

# ============================================================
# 🔗 الاتصال بـ Firebase
# ============================================================

firestore_db = None

def init_firebase():
    """تهيئة الاتصال بـ Firebase"""
    global firestore_db
    
    if FIREBASE_CREDENTIALS_JSON:
        try:
            cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            firestore_db = firestore.client()
            logger.info("✅ اتصلت بـ Firebase Firestore")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال بـ Firebase: {e}")
            return False
    else:
        logger.warning("⚠️ FIREBASE_CREDENTIALS_JSON مش موجود")
        return False

# ============================================================
# 🗺️ عمليات Graph (خريطة بحر)
# ============================================================

def graph_add_node(node_id, label, category, facts_list, links_list=None):
    """إضافة عقدة جديدة في الجراف"""
    if firestore_db is None:
        return False, "Firestore مش متصل"
    
    try:
        doc_ref = firestore_db.collection(GRAPH_COLLECTION).document(node_id)
        doc_ref.set({
            "label": label,
            "category": category,
            "size": 16,
            "facts": facts_list,
            "links": links_list or [],
            "deleted": False,
            "updatedAt": int(time.time() * 1000)
        })
        logger.info(f"✅ عقدة جديدة: {label}")
        return True, "تم"
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة عقدة: {e}")
        return False, str(e)

def graph_edit_node(node_id, new_fact):
    """تعديل عقدة موجودة"""
    if firestore_db is None:
        return False, "Firestore مش متصل"
    
    try:
        doc_ref = firestore_db.collection(GRAPH_COLLECTION).document(node_id)
        doc_snap = doc_ref.get()
        
        if not doc_snap.exists or doc_snap.to_dict().get("deleted"):
            return False, "ما لقيتش العنصر"
        
        data = doc_snap.to_dict()
        updated_facts = data.get("facts", []) + [new_fact]
        
        doc_ref.set({
            **data,
            "facts": updated_facts,
            "updatedAt": int(time.time() * 1000)
        })
        logger.info(f"✅ تعديل عقدة: {node_id}")
        return True, "تم"
    except Exception as e:
        logger.error(f"❌ خطأ في التعديل: {e}")
        return False, str(e)

def graph_delete_node(node_id):
    """حذف عقدة (soft delete)"""
    if firestore_db is None:
        return False, "Firestore مش متصل"
    
    try:
        doc_ref = firestore_db.collection(GRAPH_COLLECTION).document(node_id)
        doc_snap = doc_ref.get()
        
        if not doc_snap.exists or doc_snap.to_dict().get("deleted"):
            return False, "ما لقيتش العنصر"
        
        doc_ref.set({"deleted": True, "updatedAt": int(time.time() * 1000)}, merge=True)
        logger.info(f"✅ حذف عقدة: {node_id}")
        return True, "تم"
    except Exception as e:
        logger.error(f"❌ خطأ في الحذف: {e}")
        return False, str(e)

def graph_list_nodes():
    """عرض كل العقد الموجودة"""
    if firestore_db is None:
        return []
    
    try:
        docs = firestore_db.collection(GRAPH_COLLECTION).stream()
        result = []
        for d in docs:
            data = d.to_dict()
            if not data.get("deleted"):
                result.append({
                    "id": d.id,
                    "label": data.get("label", d.id),
                    "category": data.get("category", "?"),
                    "facts": data.get("facts", [])
                })
        return result
    except Exception as e:
        logger.error(f"❌ خطأ في جلب العقد: {e}")
        return []

def graph_get_node(node_id):
    """جلب عقدة واحدة"""
    if firestore_db is None:
        return None
    
    try:
        doc = firestore_db.collection(GRAPH_COLLECTION).document(node_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"❌ خطأ في جلب العقدة: {e}")
        return None

# ============================================================
# 💬 عمليات Conversations
# ============================================================

def save_conversation(user_id, user_message, assistant_response):
    """حفظ محادثة"""
    if firestore_db is None:
        return False
    
    try:
        doc_ref = firestore_db.collection(CONVERSATIONS_COLLECTION).document(str(user_id))
        # فحص الحجم — لو اقترب من الـ 200 رسالة امسح القديم
        try:
            existing = doc_ref.get()
            if existing.exists:
                msgs = existing.to_dict().get("messages", [])
                if len(msgs) >= 200:
                    doc_ref.update({"messages": msgs[-100:]})  # سيب آخر 100 بس
        except Exception:
            pass
        doc_ref.set({
            "messages": firestore.ArrayUnion([
                {
                    "user": user_message,
                    "assistant": assistant_response,
                    "timestamp": int(time.time() * 1000)
                }
            ])
        }, merge=True)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ المحادثة: {e}")
        return False

def get_conversation_history(user_id, limit=50):
    """جلب سجل المحادثات"""
    if firestore_db is None:
        return []
    
    try:
        doc = firestore_db.collection(CONVERSATIONS_COLLECTION).document(str(user_id)).get()
        if doc.exists:
            messages = doc.to_dict().get("messages", [])
            return messages[-limit:]
        return []
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المحادثات: {e}")
        return []

# ============================================================
# ⏰ عمليات Reminders
# ============================================================

def save_reminder(user_id, text, send_at):
    """حفظ تذكير"""
    if firestore_db is None:
        return False
    
    try:
        firestore_db.collection(REMINDERS_COLLECTION).document().set({
            "user_id": user_id,
            "text": text,
            "send_at": send_at,
            "sent": False,
            "created_at": int(time.time() * 1000)
        })
        logger.info(f"✅ تذكير جديد: {text}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ التذكير: {e}")
        return False

def get_pending_reminders():
    """جلب التذكيرات المعلقة"""
    if firestore_db is None:
        return []
    
    try:
        now = int(time.time() * 1000)
        docs = firestore_db.collection(REMINDERS_COLLECTION).where(
            "sent", "==", False
        ).where("send_at", "<=", now).stream()
        
        reminders = []
        for doc in docs:
            reminders.append({
                "id": doc.id,
                **doc.to_dict()
            })
        return reminders
    except Exception as e:
        logger.error(f"❌ خطأ في جلب التذكيرات: {e}")
        return []

def delete_reminder(reminder_id):
    """حذف تذكير واحد من Firestore"""
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(REMINDERS_COLLECTION).document(reminder_id).delete()
        logger.info(f"✅ تم حذف التذكير: {reminder_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حذف التذكير: {e}")
        return False

def delete_all_reminders():
    """حذف كل التذكيرات من Firestore"""
    if firestore_db is None:
        return 0
    try:
        docs = firestore_db.collection(REMINDERS_COLLECTION).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        logger.info(f"✅ تم حذف {count} تذكيرات")
        return count
    except Exception as e:
        logger.error(f"❌ خطأ في حذف كل التذكيرات: {e}")
        return 0

def list_all_reminders():
    """جلب كل التذكيرات (مرسلة وغير مرسلة)"""
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(REMINDERS_COLLECTION).order_by(
            "send_at", direction="ASCENDING"
        ).stream()
        reminders = []
        for doc in docs:
            reminders.append({"id": doc.id, **doc.to_dict()})
        return reminders
    except Exception as e:
        logger.error(f"❌ خطأ في جلب كل التذكيرات: {e}")
        return []

def mark_reminder_sent(reminder_id):
    """تعليم التذكير كـ مُرسل"""
    if firestore_db is None:
        return False
    
    try:
        firestore_db.collection(REMINDERS_COLLECTION).document(reminder_id).set(
            {"sent": True},
            merge=True
        )
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث التذكير: {e}")
        return False

# ============================================================
# 👥 عمليات Clients
# ============================================================

def save_client(client_data):
    """حفظ بيانات عميل"""
    if firestore_db is None:
        return False
    
    try:
        client_id = client_data.get("id") or client_data.get("name", "client")
        firestore_db.collection(CLIENTS_COLLECTION).document(client_id).set(client_data)
        logger.info(f"✅ عميل: {client_data.get('name')}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ العميل: {e}")
        return False

def get_client(client_id):
    """جلب بيانات عميل"""
    if firestore_db is None:
        return None
    
    try:
        doc = firestore_db.collection(CLIENTS_COLLECTION).document(client_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"❌ خطأ في جلب العميل: {e}")
        return None

# ============================================================
# 🏢 عمليات Office Tasks
# ============================================================

def save_office_task(task_data):
    """حفظ مهمة مكتب"""
    if firestore_db is None:
        return False
    
    try:
        firestore_db.collection(OFFICE_TASKS_COLLECTION).document().set({
            **task_data,
            "created_at": int(time.time() * 1000)
        })
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ مهمة المكتب: {e}")
        return False

def get_office_tasks(status=None):
    """جلب مهام المكتب"""
    if firestore_db is None:
        return []
    
    try:
        query = firestore_db.collection(OFFICE_TASKS_COLLECTION)
        if status:
            query = query.where("status", "==", status)
        
        docs = query.stream()
        tasks = []
        for doc in docs:
            tasks.append({
                "id": doc.id,
                **doc.to_dict()
            })
        return tasks
    except Exception as e:
        logger.error(f"❌ خطأ في جلب مهام المكتب: {e}")
        return []

# ============================================================
# 🏗️ عمليات Site Projects
# ============================================================

def save_site_project(project_data):
    """حفظ مشروع موقع"""
    if firestore_db is None:
        return False
    
    try:
        project_id = project_data.get("id") or project_data.get("name", "project")
        firestore_db.collection(SITE_PROJECTS_COLLECTION).document(project_id).set(project_data)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ المشروع: {e}")
        return False

def get_site_projects():
    """جلب مشاريع الموقع"""
    if firestore_db is None:
        return []
    
    try:
        docs = firestore_db.collection(SITE_PROJECTS_COLLECTION).stream()
        projects = []
        for doc in docs:
            projects.append({
                "id": doc.id,
                **doc.to_dict()
            })
        return projects
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المشاريع: {e}")
        return []

# ============================================================
# 👁️ عمليات Ain Al Khabeer
# ============================================================

def save_ain_al_khabeer_log(log_data):
    """حفظ سجل عين الخبير"""
    if firestore_db is None:
        return False
    
    try:
        firestore_db.collection(AIN_AL_KHABEER_COLLECTION).document().set({
            **log_data,
            "timestamp": int(time.time() * 1000)
        })
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ السجل: {e}")
        return False

def get_ain_al_khabeer_logs(limit=50):
    """جلب السجلات"""
    if firestore_db is None:
        return []
    
    try:
        docs = firestore_db.collection(AIN_AL_KHABEER_COLLECTION).order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        ).limit(limit).stream()
        
        logs = []
        for doc in docs:
            logs.append({
                "id": doc.id,
                **doc.to_dict()
            })
        return logs
    except Exception as e:
        logger.error(f"❌ خطأ في جلب السجلات: {e}")
        return []

# ============================================================
# 🧠 عمليات الذاكرة الدائمة (Persistent Memory)
# ============================================================

def get_memory_summary(user_id):
    """
    جلب ملخص الذاكرة الدائمة لمستخدم معيّن.
    الذاكرة دي بتتراكم عبر كل الجلسات، مش بس آخر شوية رسائل.
    """
    if firestore_db is None:
        return ""
    
    try:
        doc = firestore_db.collection(MEMORY_COLLECTION).document(str(user_id)).get()
        if doc.exists:
            return doc.to_dict().get("summary", "")
        return ""
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الذاكرة الدائمة: {e}")
        return ""

def save_memory_summary(user_id, summary_text):
    """حفظ/تحديث ملخص الذاكرة الدائمة لمستخدم معيّن"""
    if firestore_db is None:
        return False
    
    try:
        firestore_db.collection(MEMORY_COLLECTION).document(str(user_id)).set({
            "summary": summary_text,
            "updated_at": int(time.time() * 1000)
        })
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الذاكرة الدائمة: {e}")
        return False

# ============================================================
# 💰 عمليات المصاريف (Expenses)
# ============================================================

def add_expense(amount, category, description="", project=None):
    """
    إضافة مصروف جديد
    
    Args:
        amount: المبلغ (رقم)
        category: التصنيف (زي: مواد خام، عمالة، تسويق، مكتب، شخصي، أخرى)
        description: وصف مختصر (اختياري)
        project: اسم المشروع المرتبط (اختياري)
    """
    if firestore_db is None:
        return False, "Firestore مش متصل"
    
    try:
        firestore_db.collection(EXPENSES_COLLECTION).document().set({
            "amount": float(amount),
            "category": category,
            "description": description,
            "project": project,
            "date": now_timestamp_str(),
            "created_at": int(time.time() * 1000)
        })
        logger.info(f"💰 مصروف جديد: {amount} جنيه — {category}")
        return True, "تم"
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ المصروف: {e}")
        return False, str(e)

def now_timestamp_str():
    """وقت حالي كنص، بدون استيراد دائري مع utils.time_utils"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def get_expenses(limit=100):
    """جلب كل المصاريف (الأحدث أولاً)"""
    if firestore_db is None:
        return []
    
    try:
        docs = firestore_db.collection(EXPENSES_COLLECTION).order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).limit(limit).stream()
        
        expenses = []
        for doc in docs:
            expenses.append({"id": doc.id, **doc.to_dict()})
        return expenses
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المصاريف: {e}")
        return []

def delete_expense(expense_id: str):
    """حذف مصروف بالـ ID"""
    if firestore_db is None:
        return False, "Firestore مش متصل"
    try:
        firestore_db.collection(EXPENSES_COLLECTION).document(expense_id).delete()
        return True, "تم الحذف"
    except Exception as e:
        return False, str(e)

def get_expense_summary(category=None, project=None):
    """
    ملخص المصاريف: الإجمالي + التقسيم حسب التصنيف
    
    Args:
        category: فلترة بتصنيف معيّن (اختياري)
        project: فلترة بمشروع معيّن (اختياري)
    
    Returns:
        dict فيه total والتفاصيل حسب التصنيف
    """
    expenses = get_expenses(limit=1000)
    
    if category:
        expenses = [e for e in expenses if e.get("category") == category]
    if project:
        expenses = [e for e in expenses if e.get("project") == project]
    
    total = sum(e.get("amount", 0) for e in expenses)
    
    by_category = {}
    for e in expenses:
        cat = e.get("category", "غير مصنّف")
        by_category[cat] = by_category.get(cat, 0) + e.get("amount", 0)
    
    return {
        "total": total,
        "count": len(expenses),
        "by_category": by_category
    }

# ============================================================
# 💳 عمليات حالة دفع الأقساط (Loans)
# ============================================================

_LOANS_DOC_ID = "paid_status"

def get_loan_paid_map():
    """جلب خريطة حالة الدفع لكل الأقساط ({'valu_0': True, ...})"""
    if firestore_db is None:
        return {}
    
    try:
        doc = firestore_db.collection(LOANS_COLLECTION).document(_LOANS_DOC_ID).get()
        if doc.exists:
            return doc.to_dict().get("paid", {})
        return {}
    except Exception as e:
        logger.error(f"❌ خطأ في جلب حالة الأقساط: {e}")
        return {}

# ملاحظة: الكتابة المباشرة لحالة الدفع (save_loan_paid_status) اتشالت في Stage 2
# (ADAM Self-State & Observation System). الكتابة دلوقتي بتمر حصريًا من
# services/loan_commands.py عبر event_store.record_event_with_write (كتابة
# ذرية مع تسجيل الحدث). مفيش مسار كتابة تاني هنا عن قصد.

# ============================================================
# 👤 Human Model — نموذج أحمد
# ============================================================

HUMAN_MODEL_COLLECTION = "adam_human_model"
AHMED_DOC_ID = "ahmed_gowaida"

def get_human_model():
    """جلب Human Model لأحمد من Firestore"""
    if firestore_db is None:
        return {}
    try:
        doc = firestore_db.collection(HUMAN_MODEL_COLLECTION).document(AHMED_DOC_ID).get()
        if doc.exists:
            return doc.to_dict()
        else:
            # إنشاء النموذج الأساسي لأول مرة
            default_model = {
                "name": "أحمد",
                "company": "Bahr Designs",
                "industry": "Interior Architecture & Fit-Out",
                "spouse": "إسراء",
                "spouse_birthday": "",
                "daughter": "غالية",
                "daughter_birthday": "16 أبريل",
                "morning_time": "08:00",
                "timezone": "Africa/Cairo",
                "communication_style": "مباشر وعملي",
                "created_at": int(time.time() * 1000)
            }
            firestore_db.collection(HUMAN_MODEL_COLLECTION).document(AHMED_DOC_ID).set(default_model)
            logger.info("✅ تم إنشاء Human Model لأحمد")
            return default_model
    except Exception as e:
        logger.error(f"❌ خطأ في جلب Human Model: {e}")
        return {}

def update_human_model(key: str, value: str):
    """تحديث حقل واحد في Human Model"""
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(HUMAN_MODEL_COLLECTION).document(AHMED_DOC_ID).set(
            {key: value, "updated_at": int(time.time() * 1000)},
            merge=True
        )
        logger.info(f"✅ Human Model updated: {key} = {value}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث Human Model: {e}")
        return False

def update_human_model_bulk(data: dict):
    """تحديث أكتر من حقل في Human Model دفعة واحدة"""
    if firestore_db is None:
        return False
    try:
        data["updated_at"] = int(time.time() * 1000)
        firestore_db.collection(HUMAN_MODEL_COLLECTION).document(AHMED_DOC_ID).set(
            data, merge=True
        )
        logger.info(f"✅ Human Model bulk updated: {list(data.keys())}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في التحديث الجماعي لـ Human Model: {e}")
        return False

# ============================================================
# 🏗️ Bahr OS Integration — قراءة المشاريع (Read-Only)
# ============================================================

BAHR_SITES_COLLECTION = "bahrSites"
DEPA_PROJECTS_COLLECTION = "depaProjects"

def create_bahr_project(client, area, supervisors=None, status="active"):
    """إنشاء مشروع جديد في Bahr OS"""
    if firestore_db is None:
        return None, "Firestore مش متصل"
    try:
        import uuid
        from utils.time_utils import now_cairo
        project_id = "PRJ-" + str(uuid.uuid4())[:8].upper()
        data = {
            "client": client,
            "area": float(area) if area else 0,
            "status": status,
            "allowedSupervisors": supervisors or [],
            "createdBy": "ADAM",
            "createdAt": now_cairo().isoformat(),
            "items": []
        }
        firestore_db.collection("projects").document(project_id).set(data)
        logger.info(f"✅ مشروع جديد: {project_id} — {client}")
        return project_id, "تم"
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء المشروع: {e}")
        return None, str(e)

def update_bahr_project(project_id, **kwargs):
    """تعديل بيانات مشروع موجود"""
    if firestore_db is None:
        return False, "Firestore مش متصل"
    try:
        from utils.time_utils import now_cairo
        update_data = {"updatedAt": now_cairo().isoformat()}
        if "client"      in kwargs: update_data["client"]             = kwargs["client"]
        if "area"        in kwargs: update_data["area"]               = float(kwargs["area"])
        if "supervisors" in kwargs: update_data["allowedSupervisors"] = kwargs["supervisors"]
        if "status"      in kwargs: update_data["status"]             = kwargs["status"]
        firestore_db.collection("projects").document(project_id).set(update_data, merge=True)
        return True, "تم التعديل"
    except Exception as e:
        return False, str(e)

def delete_bahr_project(project_id):
    """حذف مشروع"""
    if firestore_db is None:
        return False, "Firestore مش متصل"
    try:
        firestore_db.collection("projects").document(project_id).delete()
        return True, "تم الحذف"
    except Exception as e:
        return False, str(e)

def add_bahr_site(project_id, site_name, supervisors=None):
    """إضافة موقع جديد في Bahr Sites"""
    if firestore_db is None:
        return None, "Firestore مش متصل"
    try:
        import uuid
        from utils.time_utils import now_cairo
        site_id = "SITE-" + str(uuid.uuid4())[:8].upper()
        data = {
            "projectId": project_id,
            "name": site_name,
            "allowedSupervisors": supervisors or [],
            "status": "نشط",
            "createdAt": now_cairo().isoformat(),
            "items": []
        }
        firestore_db.collection(BAHR_SITES_COLLECTION).document(site_id).set(data)
        return site_id, "تم"
    except Exception as e:
        return None, str(e)

def get_bahr_projects(limit=20):
    """جلب مشاريع Bahr OS من Firestore (read-only)"""
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection("projects").limit(limit).stream()
        projects = []
        for doc in docs:
            data = doc.to_dict() or {}
            projects.append({
                "id": doc.id,
                "client": data.get("client", ""),
                "area": data.get("area", ""),
                "status": data.get("status", ""),
                "supervisors": data.get("allowedSupervisors", []),
                "created_by": data.get("createdBy", ""),
            })
        return projects
    except Exception as e:
        logger.error(f"❌ خطأ في جلب مشاريع Bahr OS: {e}")
        return []

def get_bahr_sites(limit=20):
    """جلب مواقع Bahr Sites من Firestore (read-only)"""
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(BAHR_SITES_COLLECTION).limit(limit).stream()
        sites = []
        for doc in docs:
            data = doc.to_dict() or {}
            supervisors = data.get("allowedSupervisors", [])
            sites.append({
                "id": doc.id,
                "client": data.get("client", ""),
                "area": data.get("area", ""),
                "status": data.get("status", "نشط"),
                "supervisors": supervisors,
                "supervisors_count": len(supervisors),
                "items_count": len(data.get("items", [])),
            })
        return sites
    except Exception as e:
        logger.error(f"❌ خطأ في جلب Bahr Sites: {e}")
        return []

def get_project_details(project_id):
    """جلب تفاصيل مشروع معين — items كـ array في الـ document"""
    if firestore_db is None:
        return {}
    try:
        doc = firestore_db.collection("projects").document(project_id).get()
        if doc.exists:
            data = doc.to_dict()
            
            # items هي array جوه الـ document مباشرة
            items = data.get("items", [])
            if not isinstance(items, list):
                items = []
            
            return {
                "id": doc.id,
                "client": data.get("client", ""),
                "area": data.get("area", ""),
                "status": data.get("status", ""),
                "supervisors": data.get("allowedSupervisors", []),
                "items": items,
                "items_count": len(items),
                "deduction_rates": data.get("deductionRates", {}),
                "final_data": data.get("finaldata", {}),
            }
        return {}
    except Exception as e:
        logger.error(f"❌ خطأ في جلب تفاصيل المشروع: {e}")
        return {}

# ============================================================
# 🔄 Recurring Reminders — التذكيرات المتكررة
# ============================================================

RECURRING_REMINDERS_COLLECTION = "recurring_reminders"

def save_recurring_reminder(text, interval_type, interval_value, chat_id, scheduled_hour=None, scheduled_minute=None):
    """
    حفظ تذكير متكرر في Firestore.
    
    Args:
        text: نص التذكير
        interval_type: daily/weekly/hourly/custom_minutes
        interval_value: رقم الفترة
        chat_id: معرف المحادثة
        scheduled_hour: ساعة محددة (0-23) لو interval_type = daily
        scheduled_minute: دقيقة محددة (0-59)
    """
    if firestore_db is None:
        return None
    try:
        doc_ref = firestore_db.collection(RECURRING_REMINDERS_COLLECTION).document()
        doc_ref.set({
            "text": text,
            "interval_type": interval_type,
            "interval_value": interval_value,
            "scheduled_hour": scheduled_hour,    # وقت محدد لو daily
            "scheduled_minute": scheduled_minute or 0,
            "chat_id": chat_id,
            "active": True,
            "created_at": int(time.time() * 1000),
            "last_sent": None
        })
        logger.info(f"✅ تذكير متكرر جديد: {text} ({interval_type})")
        return doc_ref.id
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ التذكير المتكرر: {e}")
        return None

def get_active_recurring_reminders():
    """جلب التذكيرات المتكررة النشطة"""
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(RECURRING_REMINDERS_COLLECTION).where(
            "active", "==", True
        ).stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception as e:
        logger.error(f"❌ خطأ في جلب التذكيرات المتكررة: {e}")
        return []

def update_recurring_reminder_last_sent(reminder_id):
    """تحديث آخر وقت إرسال للتذكير المتكرر"""
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(RECURRING_REMINDERS_COLLECTION).document(reminder_id).update({
            "last_sent": int(time.time() * 1000)
        })
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث التذكير المتكرر: {e}")
        return False

def delete_recurring_reminder_db(reminder_id):
    """حذف تذكير متكرر"""
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(RECURRING_REMINDERS_COLLECTION).document(reminder_id).delete()
        logger.info(f"✅ تم حذف التذكير المتكرر: {reminder_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حذف التذكير المتكرر: {e}")
        return False

# ============================================================
# 🧠 Memory Notes — Episodic Memory
# ============================================================

MEMORY_NOTES_COLLECTION = "memory_notes"

def save_memory_note(user_id: str, text: str, category: str = "", related_to: str = "") -> bool:
    """حفظ ملاحظة/حدث مهم في الذاكرة"""
    if firestore_db is None:
        return False
    try:
        import datetime as dt
        firestore_db.collection(MEMORY_NOTES_COLLECTION).document().set({
            "user_id": str(user_id),
            "text": text,
            "category": category,
            "related_to": related_to,
            "created_at": int(time.time() * 1000),
            "timestamp_str": dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        logger.info(f"🧠 Memory note saved: {text[:50]}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الملاحظة: {e}")
        return False


def save_memory_note_with_deadline(
    user_id: str,
    text: str,
    deadline_date: str,
    category: str = "مشروع",
    related_to: str = "",
    days_before: int = 3
) -> dict:
    """
    حفظ ملاحظة مع deadline وإنشاء تذكير تلقائي.
    
    Args:
        user_id: معرف المستخدم
        text: نص الملاحظة
        deadline_date: تاريخ الـ deadline (YYYY-MM-DD)
        category: تصنيف الملاحظة
        related_to: اسم المشروع أو الشخص
        days_before: كم يوم قبل الـ deadline يبعت التذكير
    
    Returns:
        {"note_id": ..., "reminder_id": ..., "reminder_date": ...}
    """
    import datetime as dt
    
    result = {"note_id": None, "reminder_id": None, "reminder_date": None}
    
    # 1. حفظ الملاحظة
    note_ok = save_memory_note(
        user_id,
        f"{text} [Deadline: {deadline_date}]",
        category,
        related_to
    )
    
    if not note_ok:
        return result
    
    # 2. حساب تاريخ التذكير
    try:
        deadline = dt.datetime.strptime(deadline_date, "%Y-%m-%d")
        reminder_dt = deadline - dt.timedelta(days=days_before)
        reminder_ms = int(reminder_dt.timestamp() * 1000)
        result["reminder_date"] = reminder_dt.strftime("%Y-%m-%d")
        
        # 3. إنشاء التذكير
        reminder_text = f"⚠️ تذكير: {text} — الـ deadline بعد {days_before} أيام ({deadline_date})"
        
        if firestore_db:
            doc_ref = firestore_db.collection(REMINDERS_COLLECTION).document()
            doc_ref.set({
                "user_id": str(user_id),
                "text": reminder_text,
                "send_at": reminder_ms,
                "sent": False,
                "created_at": int(time.time() * 1000),
                "type": "deadline_reminder"
            })
            result["reminder_id"] = doc_ref.id
            logger.info(f"✅ Deadline reminder created: {reminder_dt.strftime('%Y-%m-%d')}")
    
    except ValueError as e:
        logger.error(f"❌ خطأ في تاريخ الـ deadline: {e}")
    
    return result


def update_memory_note(note_id: str, new_text: str = None, status: str = None) -> bool:
    """
    تعديل ملاحظة موجودة أو تعليمها كـ "قديمة/ملغاة".
    
    Args:
        note_id: ID الملاحظة
        new_text: النص الجديد (اختياري)
        status: "active" / "outdated" / "cancelled"
    """
    if firestore_db is None:
        return False
    try:
        import datetime as dt
        update_data = {"updated_at": int(time.time() * 1000)}
        if new_text:
            update_data["text"] = new_text
        if status:
            update_data["status"] = status
        firestore_db.collection(MEMORY_NOTES_COLLECTION).document(note_id).update(update_data)
        logger.info(f"✅ Memory note updated: {note_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تعديل الملاحظة: {e}")
        return False

def get_upcoming_deadlines(user_id: str, days_ahead: int = 30) -> list:
    """
    جلب كل الـ deadlines الجاية مرتبة بالتاريخ.
    
    Args:
        user_id: معرف المستخدم
        days_ahead: كم يوم قدام (default: 30)
    
    Returns:
        List of notes with deadlines sorted by date
    """
    if firestore_db is None:
        return []
    try:
        import datetime as dt
        import re
        
        now = dt.datetime.now()
        future = now + dt.timedelta(days=days_ahead)
        
        # جلب الملاحظات بـ limit عشان ما تأخرش
        docs = firestore_db.collection(MEMORY_NOTES_COLLECTION)\
            .where("user_id", "==", str(user_id))\
            .limit(500)\
            .stream()
        
        deadlines = []
        for doc in docs:
            data = doc.to_dict()
            text = data.get("text", "")
            status = data.get("status", "active")
            
            if status in ["outdated", "cancelled"]:
                continue
            
            # استخراج التاريخ من النص [Deadline: YYYY-MM-DD]
            match = re.search(r'Deadline: (\d{4}-\d{2}-\d{2})', text)
            if match:
                try:
                    deadline_dt = dt.datetime.strptime(match.group(1), "%Y-%m-%d")
                    if now <= deadline_dt <= future:
                        days_remaining = (deadline_dt - now).days
                        deadlines.append({
                            "id": doc.id,
                            "text": text.replace(f" [Deadline: {match.group(1)}]", ""),
                            "deadline": match.group(1),
                            "days_remaining": days_remaining,
                            "category": data.get("category", ""),
                            "related_to": data.get("related_to", ""),
                            "urgent": days_remaining <= 3
                        })
                except ValueError:
                    continue
        
        # ترتيب حسب الأقرب
        deadlines.sort(key=lambda x: x["days_remaining"])
        
        # فحص تعارض المواعيد
        conflicts = []
        for i in range(len(deadlines)):
            for j in range(i+1, len(deadlines)):
                diff = abs(deadlines[i]["days_remaining"] - deadlines[j]["days_remaining"])
                if diff <= 7:
                    conflicts.append((deadlines[i]["deadline"], deadlines[j]["deadline"]))
        
        return {"deadlines": deadlines, "conflicts": conflicts}
    
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الـ deadlines: {e}")
        return {"deadlines": [], "conflicts": []}


def get_mood_history(user_id: str, days: int = 7) -> dict:
    """
    جلب تاريخ المزاج من آخر X أيام.
    
    Returns:
        {
            "moods": [...],
            "negative_count": int,
            "positive_count": int,
            "needs_attention": bool
        }
    """
    import datetime as dt
    
    try:
        notes = list_memory_notes(str(user_id), limit=100)
        
        cutoff = dt.datetime.now() - dt.timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        moods = []
        for note in notes:
            if note.get("category") == "مزاج":
                timestamp = note.get("timestamp", "")
                if timestamp >= cutoff_str:
                    moods.append(note)
        
        # تصنيف المزاج
        negative_words = ["تعبان", "متضايق", "مرهق", "زهقان", "مش كويس", "صعبة", "ضغط"]
        positive_words = ["مبسوط", "كويس", "نشيط", "متحمس", "رايق", "ممتاز"]
        
        negative_count = 0
        positive_count = 0
        
        for mood in moods:
            text = mood.get("text", "").lower()
            if any(w in text for w in negative_words):
                negative_count += 1
            elif any(w in text for w in positive_words):
                positive_count += 1
        
        return {
            "moods": moods,
            "negative_count": negative_count,
            "positive_count": positive_count,
            "needs_attention": negative_count >= 2
        }
    
    except Exception as e:
        logger.error(f"❌ خطأ في جلب تاريخ المزاج: {e}")
        return {"moods": [], "negative_count": 0, "positive_count": 0, "needs_attention": False}

def delete_memory_note(note_id: str) -> bool:
    """حذف ملاحظة من الذاكرة"""
    if firestore_db is None:
        return False
    try:
        firestore_db.collection(MEMORY_NOTES_COLLECTION).document(note_id).delete()
        logger.info(f"🗑️ Memory note deleted: {note_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حذف الملاحظة: {e}")
        return False

def search_memory_notes(user_id: str, keyword: str, limit: int = 10) -> list:
    """بحث في الملاحظات بـ keyword"""
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(MEMORY_NOTES_COLLECTION)\
            .where("user_id", "==", str(user_id))\
            .order_by("created_at", direction="DESCENDING")\
            .limit(100)\
            .stream()
        
        keyword_lower = keyword.lower()
        results = []
        for doc in docs:
            data = doc.to_dict()
            text = data.get("text", "").lower()
            related = data.get("related_to", "").lower()
            category = data.get("category", "").lower()
            
            if keyword_lower in text or keyword_lower in related or keyword_lower in category:
                results.append({
                    "id": doc.id,
                    "text": data.get("text", ""),
                    "category": data.get("category", ""),
                    "related_to": data.get("related_to", ""),
                    "timestamp": data.get("timestamp_str", "")
                })
                if len(results) >= limit:
                    break
        
        return results
    except Exception as e:
        logger.error(f"❌ خطأ في البحث: {e}")
        return []

def list_memory_notes(user_id: str, limit: int = 50) -> list:
    """جلب آخر الملاحظات"""
    if firestore_db is None:
        return []
    try:
        docs = firestore_db.collection(MEMORY_NOTES_COLLECTION)\
            .where("user_id", "==", str(user_id))\
            .order_by("created_at", direction="DESCENDING")\
            .limit(limit)\
            .stream()
        
        return [{
            "id": doc.id,
            "text": doc.to_dict().get("text", ""),
            "category": doc.to_dict().get("category", ""),
            "related_to": doc.to_dict().get("related_to", ""),
            "timestamp": doc.to_dict().get("timestamp_str", "")
        } for doc in docs]
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الملاحظات: {e}")
        return []
