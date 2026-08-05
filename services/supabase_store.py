# -*- coding: utf-8 -*-
"""
🐘 Supabase Store -- تنفيذات Supabase الصافية لمجموعات "دماغ آدم"

قرار أحمد الصريح (2026-08-05 مساءً): «من دلوقتي حالًا Supabase --
ميعطلنيش أبدًا الباقة بتاعت Firebase». حادثة اليوم: كوتا القراءة خلصت
(53 ألف قراءة) وآدم اتشل عن أي قراءة لباقي اليوم.

الملف ده **Supabase بس** -- صفر استيراد من firebase_service (عشان مفيش
دايرية: firebase_service هو اللي بيستورد من هنا في بلوك الأولوية بتاعه).

العقد الصارم لكل دالة هنا:
  - قراءة: بترجع القيمة عند النجاح، و **None عند أي فشل أو غياب اتصال**
    -- المنادي (بلوك الأولوية في firebase_service) هو اللي بيقرر يرجع
    لـ Firestore. None هنا معناها "مش قادر أجاوب"، مش "فاضي".
  - كتابة: True عند النجاح، False عند الفشل. الـ mirror لـ Firestore
    مسؤولية المنادي، مش هنا.

المجموعات المغطاة (اللي عندنا نسخة GitHub ليها + الجداول في 002):
  user_memory, memory_notes, conversation_messages, human_model,
  bahr_graph_nodes
"""

import time
from datetime import datetime, timezone, timedelta

from utils.logger import logger
from services import supabase_service

try:
    from zoneinfo import ZoneInfo
    CAIRO = ZoneInfo("Africa/Cairo")
except Exception:                                    # pragma: no cover
    CAIRO = timezone.utc

HUMAN_MODEL_KEY = "ahmed_gowaida"


def _client():
    return supabase_service.supabase_client


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_epoch_ms(iso_text):
    """timestamptz راجع من Supabase (نص ISO) -> epoch ms للتوافق مع
    الكولرز القديمة اللي بتتوقع رقم."""
    if not iso_text:
        return None
    try:
        return int(datetime.fromisoformat(str(iso_text).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def _display_text(row):
    """بيرجّع نص الملاحظة بالشكل اللي كل الكولرز القديمة متعودة عليه:
    الموعد النهائي متلحق بالنص. التخزين نضيف (عمود deadline منفصل)،
    بس العرض متوافق مع القديم."""
    text = row.get("text") or ""
    if row.get("deadline"):
        return f"{text} [Deadline: {row['deadline']}]"
    return text


def _note_row_to_legacy(row):
    """صف Supabase -> شكل مستند Firestore القديم اللي الكولرز بتتوقعه."""
    created_ms = _to_epoch_ms(row.get("created_at"))
    created_str = ""
    if created_ms:
        created_str = datetime.fromtimestamp(created_ms / 1000, tz=CAIRO).strftime("%Y-%m-%d %H:%M")
    return {
        "id": row.get("firestore_id") or row.get("id"),
        "user_id": row.get("user_id"),
        "text": _display_text(row),
        "category": row.get("category") or "",
        "related_to": row.get("related_to") or "",
        "status": row.get("status") or "active",
        "created_at": created_ms,
        # الكولرز القديمة بتقرا "timestamp" (من list) و"timestamp_str"
        # (من المستند الخام) -- بنرجّع الاتنين للتوافق الكامل
        "timestamp": created_str,
        "timestamp_str": created_str,
        "urgent_alert_sent": bool(row.get("urgent_alert_sent")),
    }


# ============================================================
# 🧠 user_memory -- الذاكرة الدائمة
# ============================================================

def get_memory_summary(user_id):
    """None = مش قادر أقرا (fallback)، '' = فعلاً مفيش ذاكرة لسه."""
    if _client() is None:
        return None
    try:
        resp = _client().table("user_memory").select("summary").eq(
            "user_id", str(user_id)
        ).limit(1).execute()
        if resp.data:
            return resp.data[0].get("summary") or ""
        return ""
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة الذاكرة فشلت: {str(e)[:80]}")
        return None


def save_memory_summary(user_id, summary_text):
    if _client() is None:
        return False
    try:
        _client().table("user_memory").upsert({
            "user_id": str(user_id),
            "summary": summary_text,
            "updated_at": _now_iso(),
        }, on_conflict="user_id").execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ الذاكرة فشل: {str(e)[:80]}")
        return False


# ============================================================
# 📝 memory_notes -- الملاحظات
# ============================================================

def save_memory_note(user_id, text, category="", related_to="", deadline=None,
                     firestore_id=None):
    if _client() is None:
        return False
    try:
        row = {
            "user_id": str(user_id),
            "text": text,
            "category": category or None,
            "related_to": related_to or None,
            "status": "active",
            "created_at": _now_iso(),
        }
        if deadline:
            row["deadline"] = str(deadline)
        if firestore_id:
            row["firestore_id"] = firestore_id
        _client().table("memory_notes").insert(row).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ الملاحظة فشل: {str(e)[:80]}")
        return False


def list_memory_notes(user_id, limit=50):
    if _client() is None:
        return None
    try:
        resp = _client().table("memory_notes").select("*").eq(
            "user_id", str(user_id)
        ).order("created_at", desc=True).limit(limit).execute()
        return [_note_row_to_legacy(r) for r in (resp.data or [])]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة الملاحظات فشلت: {str(e)[:80]}")
        return None


def search_memory_notes(user_id, keyword, limit=10):
    """بحث نصي -- ilike على النص والفئة والمرتبط بيه.

    ملحوظة: ده اللي كان **واقف خالص** على Firestore من 21 يوليو
    (composite index ناقص). على Postgres بيشتغل من أول يوم.
    """
    if _client() is None:
        return None
    try:
        pattern = f"%{keyword}%"
        resp = _client().table("memory_notes").select("*").eq(
            "user_id", str(user_id)
        ).or_(
            f"text.ilike.{pattern},category.ilike.{pattern},related_to.ilike.{pattern}"
        ).order("created_at", desc=True).limit(limit).execute()
        return [_note_row_to_legacy(r) for r in (resp.data or [])]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] البحث في الملاحظات فشل: {str(e)[:80]}")
        return None


def update_memory_note(note_id, new_text=None, status=None):
    """note_id هنا هو الـ firestore_id القديم (اللي الكولرز شايفينه)."""
    if _client() is None:
        return False
    try:
        patch = {"updated_at": _now_iso()}
        if new_text is not None:
            patch["text"] = new_text
        if status is not None:
            patch["status"] = status
        resp = _client().table("memory_notes").update(patch).eq(
            "firestore_id", note_id
        ).execute()
        return bool(resp.data)
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تعديل الملاحظة فشل: {str(e)[:80]}")
        return False


def get_upcoming_deadlines(user_id, days_ahead=30):
    """نفس شكل الرد القديم: {"deadlines": [...], "conflicts": [...]}.

    الفرق الجوهري: الموعد بييجي من **عمود حقيقي** مش regex على النص.
    """
    if _client() is None:
        return None
    try:
        today = datetime.now(CAIRO).date()
        future = today + timedelta(days=days_ahead)
        resp = _client().table("memory_notes").select("*").eq(
            "user_id", str(user_id)
        ).not_.is_("deadline", "null").gte(
            "deadline", today.isoformat()
        ).lte("deadline", future.isoformat()).execute()

        deadlines = []
        for row in resp.data or []:
            if (row.get("status") or "active") in ("outdated", "cancelled"):
                continue
            due = datetime.fromisoformat(row["deadline"]).date()
            days_remaining = (due - today).days
            deadlines.append({
                "id": row.get("firestore_id") or row.get("id"),
                "text": row.get("text") or "",
                "deadline": row["deadline"],
                "days_remaining": days_remaining,
                "category": row.get("category") or "",
                "related_to": row.get("related_to") or "",
                "urgent": days_remaining <= 3,
            })

        deadlines.sort(key=lambda x: x["days_remaining"])

        conflicts = []
        for i in range(len(deadlines)):
            for j in range(i + 1, len(deadlines)):
                if abs(deadlines[i]["days_remaining"] - deadlines[j]["days_remaining"]) <= 7:
                    conflicts.append((deadlines[i]["deadline"], deadlines[j]["deadline"]))

        return {"deadlines": deadlines, "conflicts": conflicts}
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة المواعيد فشلت: {str(e)[:80]}")
        return None


# ============================================================
# 💬 conversation_messages -- المحادثات
# ============================================================

def save_conversation(user_id, user_message, assistant_response):
    if _client() is None:
        return False
    try:
        _client().table("conversation_messages").insert({
            "user_id": str(user_id),
            "user_text": user_message,
            "assistant_text": assistant_response,
            "occurred_at": _now_iso(),
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ المحادثة فشل: {str(e)[:80]}")
        return False


def get_conversation_history(user_id, limit=50):
    """بيرجع نفس شكل عناصر الـ messages القديمة: {user, assistant, timestamp}."""
    if _client() is None:
        return None
    try:
        resp = _client().table("conversation_messages").select(
            "user_text, assistant_text, occurred_at"
        ).eq("user_id", str(user_id)).order(
            "occurred_at", desc=True
        ).limit(limit).execute()

        rows = list(reversed(resp.data or []))
        return [
            {
                "user": r.get("user_text") or "",
                "assistant": r.get("assistant_text") or "",
                "timestamp": _to_epoch_ms(r.get("occurred_at")) or 0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة المحادثات فشلت: {str(e)[:80]}")
        return None


def search_conversations(user_id, keyword, limit=10):
    """بحث نصي في تاريخ المحادثات كله.

    القدرة دي كانت **مستحيلة** على Firestore: الرسايل كانت متخزنة مصفوفة
    جوه مستند واحد، ومفيش أي استعلام بيدخل جوه المصفوفات. على Postgres
    هي ilike عادية.
    """
    if _client() is None:
        return None
    try:
        pattern = f"%{keyword}%"
        resp = _client().table("conversation_messages").select(
            "user_text, assistant_text, occurred_at"
        ).eq("user_id", str(user_id)).or_(
            f"user_text.ilike.{pattern},assistant_text.ilike.{pattern}"
        ).order("occurred_at", desc=True).limit(limit).execute()

        results = []
        for r in resp.data or []:
            when = ""
            ms = _to_epoch_ms(r.get("occurred_at"))
            if ms:
                when = datetime.fromtimestamp(ms / 1000, tz=CAIRO).strftime("%Y-%m-%d %H:%M")
            results.append({
                "user": r.get("user_text") or "",
                "assistant": r.get("assistant_text") or "",
                "when": when,
            })
        return results
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] البحث في المحادثات فشل: {str(e)[:80]}")
        return None


# ============================================================
# 👤 human_model -- نموذج أحمد
# ============================================================

def get_human_model():
    if _client() is None:
        return None
    try:
        resp = _client().table("human_model").select("data").eq(
            "user_key", HUMAN_MODEL_KEY
        ).limit(1).execute()
        if resp.data:
            return resp.data[0].get("data") or {}
        return None      # مفيش صف = خلّي firebase_service يتصرف بمساره القديم
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة الـ Human Model فشلت: {str(e)[:80]}")
        return None


def update_human_model(key, value):
    """دمج مفتاح واحد جوه الـ jsonb -- read-modify-write."""
    if _client() is None:
        return False
    try:
        current = get_human_model() or {}
        current[key] = value
        _client().table("human_model").upsert({
            "user_key": HUMAN_MODEL_KEY,
            "data": current,
            "updated_at": _now_iso(),
        }, on_conflict="user_key").execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تعديل الـ Human Model فشل: {str(e)[:80]}")
        return False


def update_human_model_bulk(data):
    if _client() is None:
        return False
    try:
        current = get_human_model() or {}
        current.update(data or {})
        _client().table("human_model").upsert({
            "user_key": HUMAN_MODEL_KEY,
            "data": current,
            "updated_at": _now_iso(),
        }, on_conflict="user_key").execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تعديل الـ Human Model (bulk) فشل: {str(e)[:80]}")
        return False


# ============================================================
# 🗺️ bahr_graph_nodes -- الجراف
# ============================================================

def graph_add_node(node_id, label, category, facts_list, links_list=None):
    if _client() is None:
        return False
    try:
        _client().table("bahr_graph_nodes").upsert({
            "firestore_id": node_id,
            "label": label,
            "category": category,
            "facts": facts_list or [],
            "links": links_list or [],
            "size": 16,
            "deleted": False,
            "updated_at": _now_iso(),
        }, on_conflict="firestore_id").execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] إضافة عقدة فشلت: {str(e)[:80]}")
        return False


def graph_edit_node(node_id, new_fact):
    """بيرجع True/False للنجاح، أو None لو مش قادر يقرا أصلاً (fallback)."""
    if _client() is None:
        return None
    try:
        resp = _client().table("bahr_graph_nodes").select("facts, deleted").eq(
            "firestore_id", node_id
        ).limit(1).execute()
        if not resp.data or resp.data[0].get("deleted"):
            return False
        facts = (resp.data[0].get("facts") or []) + [new_fact]
        _client().table("bahr_graph_nodes").update({
            "facts": facts, "updated_at": _now_iso(),
        }).eq("firestore_id", node_id).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تعديل عقدة فشل: {str(e)[:80]}")
        return None


def graph_delete_node(node_id):
    if _client() is None:
        return None
    try:
        resp = _client().table("bahr_graph_nodes").select("deleted").eq(
            "firestore_id", node_id
        ).limit(1).execute()
        if not resp.data or resp.data[0].get("deleted"):
            return False
        _client().table("bahr_graph_nodes").update({
            "deleted": True, "updated_at": _now_iso(),
        }).eq("firestore_id", node_id).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حذف عقدة فشل: {str(e)[:80]}")
        return None


def graph_list_nodes():
    if _client() is None:
        return None
    try:
        resp = _client().table("bahr_graph_nodes").select(
            "firestore_id, label, category, facts"
        ).eq("deleted", False).execute()
        return [
            {
                "id": r.get("firestore_id"),
                "label": r.get("label") or r.get("firestore_id"),
                "category": r.get("category") or "?",
                "facts": r.get("facts") or [],
            }
            for r in (resp.data or [])
        ]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة العقد فشلت: {str(e)[:80]}")
        return None


def graph_get_node(node_id):
    if _client() is None:
        return None
    try:
        resp = _client().table("bahr_graph_nodes").select("*").eq(
            "firestore_id", node_id
        ).limit(1).execute()
        if not resp.data:
            return None
        r = resp.data[0]
        return {
            "label": r.get("label"),
            "category": r.get("category"),
            "facts": r.get("facts") or [],
            "links": r.get("links") or [],
            "deleted": bool(r.get("deleted")),
            "size": r.get("size", 16),
        }
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة عقدة فشلت: {str(e)[:80]}")
        return None
