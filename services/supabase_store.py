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


def _ilike_pattern(keyword):
    """نمط ilike آمن لاستخدامه جوه or_() بتاعة PostgREST.

    باگ اتمسك بالتجربة الحية (2026-08-05 مساءً): كلمة بحث فيها فاصلة --
    زي "1,232,502" -- كانت بتكسر شجرة المنطق في PostgREST لأن الفاصلة
    بتتفسر كفاصل بين الشروط ("failed to parse logic tree"). التغليف
    بعلامات اقتباس مزدوجة بيخلي القيمة حرفية مهما كان فيها.
    """
    safe = str(keyword).replace('"', "").replace("\\", "")
    return f'"%{safe}%"'


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
        pattern = _ilike_pattern(keyword)
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
        pattern = _ilike_pattern(keyword)
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
# 💰 قاعدة الأسعار -- price_base (+ المدى من/إلى، قرار أحمد 2026-08-06)
# ============================================================

def _price_display(price, price_max):
    """300.0, 800.0 -> "300-800" | 75.0, None -> "75" -- نفس شكل النص القديم."""
    def trim(x):
        f = float(x)
        return str(int(f)) if f == int(f) else str(f)
    if price_max is not None:
        return f"{trim(price)}-{trim(price_max)}"
    return trim(price)


def all_price_docs():
    """كل الأسعار بالشكل القديم اللي format_price_entries متعودة عليه.
    None عند أي فشل -- fallback لـ Firestore."""
    if _client() is None:
        return None
    try:
        resp = _client().table("price_base").select("*").execute()
        docs = []
        for r in resp.data or []:
            docs.append({
                "item": r.get("item") or "",
                "price": _price_display(r.get("price"), r.get("price_max")),
                "unit": r.get("unit") or "",
                "note": r.get("note") or "",
                "source": r.get("source") or "ahmed",
                "updated_at": r.get("updated_at") or "",
                "history": [],
            })
        return docs
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة الأسعار فشلت: {str(e)[:80]}")
        return None


def save_price_row(item, normalized, price_min, price_max, unit, note):
    """حفظ/تحديث سعر مع أرشفة القيمة القديمة في price_base_history.

    بيرجع (نجح؟، نص_السعر_القديم_أو_None).
    """
    if _client() is None:
        return False, None
    try:
        existing = _client().table("price_base").select("*").eq(
            "normalized", normalized
        ).limit(1).execute()

        old_display = None
        row = {
            "normalized": normalized,
            "item": item,
            "price": price_min,
            "price_max": price_max,
            "unit": unit or None,
            "note": note or None,
            "source": "ahmed",
            "updated_at": _now_iso(),
        }

        if existing.data:
            current = existing.data[0]
            changed = (float(current.get("price") or 0) != float(price_min)
                       or (current.get("price_max") or None) != (price_max or None))
            if changed:
                old_display = _price_display(current.get("price"), current.get("price_max"))
                _client().table("price_base_history").insert({
                    "price_base_id": current["id"],
                    "price": current.get("price"),
                    "recorded_at": current.get("updated_at"),
                }).execute()
            _client().table("price_base").update(row).eq("id", current["id"]).execute()
        else:
            _client().table("price_base").insert(row).execute()

        return True, old_display
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ السعر فشل: {str(e)[:80]}")
        return False, None




# ============================================================
# 💳 المالية -- القروض والمصاريف والقرارات وسجل الأحداث
# ============================================================
# آخر قطعة في الهجرة (2026-08-06): البيانات اتستوردت واتحقق منها صف صف،
# ودي دوال القراية/الكتابة اللي بتخلي Firestore شبكة أمان بس.

def get_loan_paid_map():
    """{identity_key: paid} -- None عند الفشل (المنادي يقرر الـ fallback).

    العقد الثلاثي محفوظ: dict = نجاح، {} = فعلاً مفيش صفوف،
    None = **فشل قراءة** (وده اللي بيمنع "صفر مدفوع" الكاذبة).
    """
    if _client() is None:
        return None
    try:
        resp = _client().table("loan_installment_status").select(
            "identity_key, paid"
        ).execute()
        return {r["identity_key"]: bool(r["paid"]) for r in (resp.data or [])}
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة خريطة الأقساط فشلت: {str(e)[:80]}")
        return None


def save_loan_status(identity_key, paid):
    if _client() is None:
        return False
    try:
        program_id, _, index_str = identity_key.rpartition("_")
        _client().table("loan_installment_status").upsert({
            "identity_key": identity_key,
            "program_id": program_id,
            "installment_index": int(index_str) if index_str.isdigit() else -1,
            "paid": bool(paid),
            "updated_at": _now_iso(),
        }, on_conflict="identity_key").execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ حالة القسط فشل ({identity_key}): {str(e)[:80]}")
        return False


def insert_event(event):
    """تسجيل حدث في سجل الأحداث -- شكل الحدث زي بتاع event_store بالظبط."""
    if _client() is None:
        return False
    try:
        entity = event.get("entity") or {}
        chat_id = event.get("chat_id")
        _client().table("adam_events").insert({
            "firestore_id": event.get("event_id"),
            "event_id": event.get("event_id"),
            "entity_type": entity.get("type") or "",
            "entity_id": str(entity.get("id") or ""),
            "attribute": event.get("attribute") or "",
            "previous_value": event.get("previous_value"),
            "new_value": event.get("new_value"),
            "source": event.get("source") or "unknown",
            "actor": event.get("actor") or "",
            "chat_id": str(chat_id) if chat_id is not None else None,
            "raw_context": event.get("raw_context") or {},
            "metadata": event.get("metadata") or {},
            "occurred_at": event.get("occurred_at"),
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تسجيل الحدث فشل: {str(e)[:80]}")
        return False


def _event_row_to_legacy(r):
    """صف Supabase -> شكل الحدث القديم اللي كل القراء متعودين عليه."""
    return {
        "event_id": r.get("event_id"),
        "entity": {"type": r.get("entity_type"), "id": r.get("entity_id")},
        "entity_key": f"{r.get('entity_type')}:{r.get('entity_id')}",
        "type_attribute_key": f"{r.get('entity_type')}:{r.get('attribute')}",
        "attribute": r.get("attribute"),
        "previous_value": r.get("previous_value"),
        "new_value": r.get("new_value"),
        "source": r.get("source"),
        "actor": r.get("actor"),
        "chat_id": r.get("chat_id"),
        "raw_context": r.get("raw_context") or {},
        "metadata": r.get("metadata") or {},
        "occurred_at": r.get("occurred_at"),
    }


def get_event(event_id):
    if _client() is None:
        return None
    try:
        resp = _client().table("adam_events").select("*").eq(
            "event_id", event_id
        ).limit(1).execute()
        if not resp.data:
            return {"__missing__": True}
        return _event_row_to_legacy(resp.data[0])
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة حدث فشلت: {str(e)[:80]}")
        return None


def get_events_for_entity(entity_type, entity_id, limit=200):
    """أحدث limit حدث، مرتبين تصاعديًا (العقد القديم: events[-1] هو الأحدث).

    الترتيب هنا **صح فعلاً** لأول مرة: على Firestore الفهرس المركب كان
    ناقص من 21 يوليو والاستعلام كان بيرجع عيّنة عشوائية.
    """
    if _client() is None:
        return None
    try:
        resp = _client().table("adam_events").select("*").eq(
            "entity_type", entity_type
        ).eq("entity_id", str(entity_id)).order(
            "occurred_at", desc=True
        ).limit(limit).execute()
        rows = list(reversed(resp.data or []))
        return [_event_row_to_legacy(r) for r in rows]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة أحداث الكيان فشلت: {str(e)[:80]}")
        return None


def get_events_by_type_and_attribute(entity_type, attribute, limit=500):
    if _client() is None:
        return None
    try:
        resp = _client().table("adam_events").select("*").eq(
            "entity_type", entity_type
        ).eq("attribute", attribute).order(
            "occurred_at", desc=True
        ).limit(limit).execute()
        rows = list(reversed(resp.data or []))
        return [_event_row_to_legacy(r) for r in rows]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة أحداث النوع فشلت: {str(e)[:80]}")
        return None


def add_expense_row(amount, category, description, project):
    if _client() is None:
        return False
    try:
        _client().table("expenses").insert({
            "amount": float(amount),
            "category": category,
            "description": description or None,
            "project": project or None,
            "occurred_at": _now_iso(),
            "created_at": _now_iso(),
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ المصروف فشل: {str(e)[:80]}")
        return False


def list_expenses(limit=100):
    """الأحدث أولًا، بالشكل القديم (date نص قاهرة، created_at رقم)."""
    if _client() is None:
        return None
    try:
        resp = _client().table("expenses").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        out = []
        for r in resp.data or []:
            occurred_ms = _to_epoch_ms(r.get("occurred_at"))
            date_str = ""
            if occurred_ms:
                date_str = datetime.fromtimestamp(
                    occurred_ms / 1000, tz=CAIRO
                ).strftime("%Y-%m-%d %H:%M")
            out.append({
                "id": r.get("firestore_id") or r.get("id"),
                "amount": float(r.get("amount") or 0),
                "category": r.get("category") or "",
                "description": r.get("description") or "",
                "project": r.get("project"),
                "date": date_str,
                "created_at": _to_epoch_ms(r.get("created_at")) or 0,
            })
        return out
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة المصاريف فشلت: {str(e)[:80]}")
        return None


def save_decision_row(decision_text, project, status, reason, source):
    if _client() is None:
        return False
    try:
        _client().table("decision_ledger").insert({
            "decision": decision_text,
            "project": project or None,
            "status": status or "accepted",
            "reason": reason or None,
            "source": source or "conversation",
            "occurred_at": _now_iso(),
            "created_at": _now_iso(),
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ القرار فشل: {str(e)[:80]}")
        return False


def list_decisions(project=None, status=None, limit=20):
    if _client() is None:
        return None
    try:
        resp = _client().table("decision_ledger").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        out = []
        for r in resp.data or []:
            created_ms = _to_epoch_ms(r.get("created_at"))
            occurred_ms = _to_epoch_ms(r.get("occurred_at"))
            date_str = ""
            if occurred_ms:
                date_str = datetime.fromtimestamp(
                    occurred_ms / 1000, tz=CAIRO
                ).strftime("%Y-%m-%d %H:%M")
            d = {
                "id": r.get("firestore_id") or r.get("id"),
                "decision": r.get("decision") or "",
                "project": r.get("project") or "",
                "status": r.get("status") or "accepted",
                "reason": r.get("reason") or "",
                "source": r.get("source") or "conversation",
                "date": date_str,
                "created_at": created_ms or 0,
            }
            if project and d["project"].lower() != str(project).lower():
                continue
            if status and d["status"] != status:
                continue
            out.append(d)
        return out
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة القرارات فشلت: {str(e)[:80]}")
        return None


def get_eye_prompt():
    """أحدث إصدار من برومبت عين الخبير -- None عند الفشل."""
    if _client() is None:
        return None
    try:
        resp = _client().table("eye_expert_prompt").select(
            "content, updated_at"
        ).order("updated_at", desc=True).limit(1).execute()
        if not resp.data:
            return {"__missing__": True}
        return resp.data[0]
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة برومبت عين الخبير فشلت: {str(e)[:80]}")
        return None


def append_eye_prompt(content, updated_by="adam"):
    """إصدار جديد -- append-only، التاريخ كله محفوظ."""
    if _client() is None:
        return False
    try:
        _client().table("eye_expert_prompt").insert({
            "content": content,
            "updated_at": _now_iso(),
            "updated_by": updated_by,
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ برومبت عين الخبير فشل: {str(e)[:80]}")
        return False


# ============================================================
# 🏪 الموردين المرجعيين -- app_settings['suppliers']
# ============================================================
# طلب أحمد (2026-08-06): موردين معتمدين ليهم مواقع فيها أسعار الخامات،
# يبقوا مرجع سوق جنب أسعاره المعتمدة (من غير ما يلمسوا price_base أبدًا).

_suppliers_cache = {"data": None, "at": 0.0}
_SUPPLIERS_TTL_SECONDS = 300


def get_suppliers():
    """قايمة الموردين، بكاش 5 دقايق -- بتتقرا مع كل رسالة فمينفعش
    تضرب قاعدة البيانات كل مرة. None لو Supabase مش متاح."""
    if _client() is None:
        return None

    now_ts = time.time()
    if _suppliers_cache["data"] is not None and (now_ts - _suppliers_cache["at"]) < _SUPPLIERS_TTL_SECONDS:
        return _suppliers_cache["data"]

    try:
        resp = _client().table("app_settings").select("value").eq(
            "key", "suppliers"
        ).limit(1).execute()
        suppliers = (resp.data[0].get("value") if resp.data else []) or []
        _suppliers_cache["data"] = suppliers
        _suppliers_cache["at"] = now_ts
        return suppliers
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة الموردين فشلت: {str(e)[:80]}")
        return None


def save_suppliers(suppliers):
    if _client() is None:
        return False
    try:
        _client().table("app_settings").upsert({
            "key": "suppliers",
            "value": suppliers,
            "updated_at": _now_iso(),
        }, on_conflict="key").execute()
        _suppliers_cache["data"] = suppliers
        _suppliers_cache["at"] = time.time()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] حفظ الموردين فشل: {str(e)[:80]}")
        return False


# ============================================================
# 🩺 أدلة صحة الأدوات -- عشان المراقبة متبقاش عمياء وقت أعطال Firestore
# ============================================================
# حادثة 2026-08-05 مساءً: تقرير الصحة طلع "0 سليمة، 13 غير معروفة، 49 غير
# مُراقَبة" -- مش لأن الأدوات بايظة، لأن المحرك بيقرا أدلته من Firestore
# والكوتا كانت خلصانة. المراقبة نفسها كانت عمياء. الأدلة بقت تتكتب وتتقرا
# من هنا الأول.

def record_health_check(row):
    """يسجّل فحص صحة (heartbeat أو real_use) -- best-effort."""
    if _client() is None:
        return False
    try:
        _client().table("tool_health_checks").insert(row).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تسجيل فحص الصحة فشل: {str(e)[:80]}")
        return False


def record_health_failure(row):
    if _client() is None:
        return False
    try:
        _client().table("tool_failures_log").insert(row).execute()
        return True
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] تسجيل الفشل فشل: {str(e)[:80]}")
        return False


def fetch_health_window(table, ts_field, cutoff_iso, cap=3000):
    """أدلة النافذة الزمنية -- None عند أي فشل (fallback لـ Firestore)."""
    if _client() is None:
        return None
    try:
        resp = _client().table(table).select("*").gte(
            ts_field, cutoff_iso
        ).limit(cap).execute()
        return resp.data or []
    except Exception as e:
        logger.warning(f"⚠️ [Supabase] قراءة أدلة الصحة فشلت ({table}): {str(e)[:80]}")
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
