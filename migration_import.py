# -*- coding: utf-8 -*-
"""
📥 استيراد نسخة GitHub لجداول Supabase -- المرحلة الأولى من التشغيل الفعلي

بيستورد الخمس مجموعات اللي عندنا نسخة GitHub ليها (آخر نسخة ليلية ناجحة):
    user_memory, memory_notes, conversations, adam_human_model,
    bahr_graph_nodes

الاستخدام:
    python migration_import.py --dir <مسار مجلد النسخة>          # استيراد
    python migration_import.py --dir <المسار> --verify           # تحقق بس

العقد:
  - **idempotent**: إعادة التشغيل ماتكررش صفوف (upsert على firestore_id
    أو مفتاح أساسي طبيعي).
  - أي قيمة مش قابلة للتحويل بثقة بتوقف الاستيراد (TransformError) --
    مش بتتحول NULL بصمت.
  - التحقق منفصل: بيقارن عدد الصفوف في Supabase بعدد المستندات في
    ملفات النسخة، مستند مستند.
"""

import argparse
import json
import os
import sys

from migration_transform import (
    TransformError, to_timestamptz, extract_deadline, blank_to_none,
)


def log(msg):
    print(msg, flush=True)


def load(backup_dir, name):
    path = os.path.join(backup_dir, f"{name}.json")
    if not os.path.exists(path):
        raise SystemExit(f"❌ ملف النسخة مش موجود: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iso(value, field):
    dt = to_timestamptz(value, field)
    return dt.isoformat() if dt else None


# ============================================================
# المستوردون -- واحد لكل مجموعة
# ============================================================

def import_user_memory(client, docs):
    rows = []
    for d in docs:
        rows.append({
            "user_id": str(d["_doc_id"]),
            "summary": d.get("summary") or "",
            "updated_at": iso(d.get("updated_at"), "user_memory.updated_at") or "1970-01-01T00:00:00Z",
        })
    if rows:
        client.table("user_memory").upsert(rows, on_conflict="user_id").execute()
    return len(rows)


def import_human_model(client, docs):
    count = 0
    for d in docs:
        data = {k: v for k, v in d.items()
                if k not in ("_doc_id", "created_at", "updated_at")}
        client.table("human_model").upsert({
            "user_key": d["_doc_id"],
            "data": data,
            "created_at": iso(d.get("created_at"), "human_model.created_at") or "1970-01-01T00:00:00Z",
            "updated_at": iso(d.get("updated_at"), "human_model.updated_at"),
        }, on_conflict="user_key").execute()
        count += 1
    return count


def import_memory_notes(client, docs):
    rows = []
    for d in docs:
        clean_text, deadline = extract_deadline(d.get("text") or "")
        rows.append({
            "firestore_id": d["_doc_id"],
            "user_id": str(d.get("user_id") or ""),
            "text": clean_text,
            "deadline": deadline.isoformat() if deadline else None,
            "category": blank_to_none(d.get("category")),
            "related_to": blank_to_none(d.get("related_to")),
            "status": d.get("status") or "active",
            "urgent_alert_sent": bool(d.get("urgent_alert_sent")),
            "created_at": iso(d.get("created_at"), "memory_notes.created_at"),
            "updated_at": iso(d.get("updated_at"), "memory_notes.updated_at"),
        })
    # دفعات -- 169 مستند في نداء واحد كتير على PostgREST
    for i in range(0, len(rows), 50):
        client.table("memory_notes").upsert(
            rows[i:i+50], on_conflict="firestore_id"
        ).execute()
    return len(rows)


def import_conversations(client, docs):
    """كل عنصر في مصفوفة messages بيبقى صف مستقل.

    idempotency هنا مختلفة: مفيش firestore_id لكل رسالة، فبنستورد بس لو
    مفيش ولا رسالة متستوردة للمستخدم ده -- إعادة التشغيل ماتكررش.
    """
    total = 0
    for d in docs:
        user_id = str(d["_doc_id"])
        existing = client.table("conversation_messages").select(
            "id", count="exact"
        ).eq("user_id", user_id).limit(1).execute()
        if (existing.count or 0) > 0:
            log(f"   ⏭️  conversation_messages للمستخدم {user_id} موجودة -- اتخطت")
            continue

        rows = []
        for m in d.get("messages") or []:
            occurred = iso(m.get("timestamp"), "conversations.timestamp")
            if occurred is None:
                raise TransformError(f"رسالة من غير timestamp للمستخدم {user_id}")
            rows.append({
                "user_id": user_id,
                "user_text": m.get("user") or "",
                "assistant_text": m.get("assistant") or "",
                "occurred_at": occurred,
            })
        for i in range(0, len(rows), 100):
            client.table("conversation_messages").insert(rows[i:i+100]).execute()
        total += len(rows)
    return total


def import_graph_nodes(client, docs):
    rows = []
    for d in docs:
        rows.append({
            "firestore_id": d["_doc_id"],
            "label": d.get("label") or d["_doc_id"],
            "category": d.get("category") or "",   # أمانة: الفاضي يفضل فاضي، مش تخمين
            "facts": d.get("facts") or [],
            "links": d.get("links") or [],
            "size": int(d.get("size") or 16),
            "deleted": bool(d.get("deleted")),
            "updated_at": iso(d.get("updatedAt"), "graph.updatedAt") or "1970-01-01T00:00:00Z",
        })
    for i in range(0, len(rows), 50):
        client.table("bahr_graph_nodes").upsert(
            rows[i:i+50], on_conflict="firestore_id"
        ).execute()
    return len(rows)




# ============================================================
# المستوردون الماليون (جولة 2026-08-06 -- بعد التصدير الكامل)
# ============================================================

def import_loans(client, docs):
    """مستند paid_status الواحد -> صف لكل قسط.

    ملحوظة حفريات (اتلقت في التصدير الفعلي): المستند فيه مفتاح حرفي
    "paid.ca_71" جنب خريطة paid الصحيحة -- ده أثر باگ الـ dotted-key
    القديم اللي التعليق في loan_commands.py بيحذر منه. بنقرا من
    الخريطة المتداخلة **بس**، والمفاتيح الشاردة بتتسجل بصوت عالي.
    """
    if not docs:
        return 0
    doc = docs[0]
    paid_map = doc.get("paid") or {}

    strays = [k for k in doc if k.startswith("paid.")]
    for stray in strays:
        log("   ⚠️ مفتاح شارد من الباگ القديم اتطنش: %r = %r (الخريطة بتقول: %r)" % (
            stray, doc[stray], paid_map.get(stray[5:], "مش موجود")))

    rows = []
    for identity_key, paid in paid_map.items():
        program_id, _, index_str = identity_key.rpartition("_")
        if not program_id or not index_str.isdigit():
            raise TransformError("identity_key مش مفهوم: %r" % identity_key)
        rows.append({
            "identity_key": identity_key,
            "program_id": program_id,
            "installment_index": int(index_str),
            "paid": bool(paid),
        })
    if rows:
        client.table("loan_installment_status").upsert(
            rows, on_conflict="identity_key"
        ).execute()
    return len(rows)


def import_expenses(client, docs):
    """مع تصحيح انحراف التوقيت: حقل date اتكتب بساعة الحاوية (UTC)."""
    from migration_transform import correct_server_naive_time
    rows = []
    for d in docs:
        occurred = correct_server_naive_time(d.get("date"), "expenses.date")
        created = to_timestamptz(d.get("created_at"), "expenses.created_at")
        rows.append({
            "firestore_id": d["_doc_id"],
            "amount": float(d.get("amount") or 0),
            "category": d.get("category") or "أخرى",
            "description": blank_to_none(d.get("description")),
            "project": blank_to_none(d.get("project")),
            "occurred_at": (occurred or created).isoformat(),
            "created_at": (created or occurred).isoformat(),
        })
    if rows:
        client.table("expenses").upsert(rows, on_conflict="firestore_id").execute()
    return len(rows)


def import_decisions(client, docs):
    from migration_transform import correct_server_naive_time
    rows = []
    for d in docs:
        occurred = correct_server_naive_time(d.get("date"), "decision.date")
        created = to_timestamptz(d.get("created_at"), "decision.created_at")
        status = d.get("status") or "accepted"
        if status not in ("accepted", "rejected", "pending"):
            raise TransformError("status مش معروف في قرار: %r" % status)
        rows.append({
            "firestore_id": d["_doc_id"],
            "decision": d.get("decision") or "",
            "project": blank_to_none(d.get("project")),
            "status": status,
            "reason": blank_to_none(d.get("reason")),
            "source": d.get("source") or "conversation",
            "occurred_at": (occurred or created).isoformat(),
            "created_at": (created or occurred).isoformat(),
        })
    for i in range(0, len(rows), 50):
        client.table("decision_ledger").upsert(
            rows[i:i+50], on_conflict="firestore_id"
        ).execute()
    return len(rows)


def import_price_base(client, docs):
    """السعر بيتحول numeric بصرامة -- قيمة مش مفهومة توقف الاستيراد."""
    from datetime import datetime as _dt, timezone as _tz
    from migration_transform import to_numeric
    count = 0
    for d in docs:
        price = to_numeric(d.get("price"), "price_base[%s].price" % d.get("item"))
        base_row = {
            "firestore_id": d["_doc_id"],
            "item": d.get("item") or "",
            "normalized": d["_doc_id"].replace("price-", ""),
            "price": price,
            "unit": blank_to_none(d.get("unit")),
            "note": blank_to_none(d.get("note")),
            "source": d.get("source") or "ahmed",
            "updated_at": (to_timestamptz(d.get("updated_at"), "price.updated_at")
                           or _dt.now(_tz.utc)).isoformat(),
        }
        resp = client.table("price_base").upsert(
            base_row, on_conflict="firestore_id"
        ).execute()
        price_id = resp.data[0]["id"]

        history = d.get("history") or []
        if history:
            existing = client.table("price_base_history").select(
                "id", count="exact"
            ).eq("price_base_id", price_id).limit(1).execute()
            if (existing.count or 0) == 0:
                hist_rows = []
                for h in history:
                    h_price = to_numeric(h.get("price"), "history.price", allow_empty=True)
                    h_at = to_timestamptz(h.get("recorded_at") or None, "history.recorded_at")
                    hist_rows.append({
                        "price_base_id": price_id,
                        "price": h_price,
                        "recorded_at": h_at.isoformat() if h_at else None,
                    })
                client.table("price_base_history").insert(hist_rows).execute()
        count += 1
    return count


def import_adam_events(client, docs):
    """4629 حدث -- العمود الفقري. دفعات 200، upsert على firestore_id."""
    rows = []
    for d in docs:
        entity = d.get("entity") or {}
        chat_id = d.get("chat_id")
        rows.append({
            "firestore_id": d["_doc_id"],
            "event_id": d.get("event_id") or d["_doc_id"],
            "entity_type": entity.get("type") or "",
            "entity_id": str(entity.get("id") or ""),
            "attribute": d.get("attribute") or "",
            "previous_value": d.get("previous_value"),
            "new_value": d.get("new_value"),
            "source": d.get("source") or "unknown",
            "actor": d.get("actor") or "",
            "chat_id": str(chat_id) if chat_id is not None else None,
            "raw_context": d.get("raw_context") or {},
            "metadata": d.get("metadata") or {},
            "occurred_at": to_timestamptz(d.get("occurred_at"), "event.occurred_at").isoformat(),
        })
    total = 0
    for i in range(0, len(rows), 200):
        client.table("adam_events").upsert(
            rows[i:i+200], on_conflict="firestore_id"
        ).execute()
        total += len(rows[i:i+200])
        log("   ... adam_events: %d/%d" % (total, len(rows)))
    return total


def import_eye_expert_prompt(client, docs):
    """المستند الواحد -> أول صف في جدول الإصدارات (append-only من هنا ورايح)."""
    from datetime import datetime as _dt, timezone as _tz
    if not docs:
        return 0
    d = docs[0]
    existing = client.table("eye_expert_prompt").select("id", count="exact").limit(1).execute()
    if (existing.count or 0) > 0:
        log("   ⏭️  eye_expert_prompt فيه إصدارات خلاص -- اتخطى")
        return 0
    client.table("eye_expert_prompt").insert({
        "content": d.get("content") or "",
        "updated_at": (to_timestamptz(d.get("updated_at"), "eye.updated_at")
                       or _dt.now(_tz.utc)).isoformat(),
        "updated_by": "migration_import",
    }).execute()
    return 1

IMPORTERS = [
    ("user_memory",       "user_memory",           import_user_memory),
    ("adam_human_model",  "human_model",           import_human_model),
    ("memory_notes",      "memory_notes",          import_memory_notes),
    ("conversations",     "conversation_messages", import_conversations),
    ("bahr_graph_nodes",  "bahr_graph_nodes",      import_graph_nodes),

    # الجولة المالية (2026-08-06)
    ("loans",             "loan_installment_status", import_loans),
    ("expenses",          "expenses",               import_expenses),
    ("decision_ledger",   "decision_ledger",        import_decisions),
    ("adam_events",       "adam_events",            import_adam_events),
    ("eye_expert_config", "eye_expert_prompt",      import_eye_expert_prompt),
    # price_base آخر واحدة: فيها قيمة مدى "850-1200" مستنية قرار أحمد
    ("price_base",        "price_base",             import_price_base),
]


# ============================================================
# التحقق
# ============================================================

def run_verify(client, backup_dir):
    log("🔍 تحقق: عدد الصفوف في Supabase مقابل ملفات النسخة")
    log("")
    problems = []

    for source, table, _ in IMPORTERS:
        docs = load(backup_dir, source)

        if source == "conversations":
            expected = sum(len(d.get("messages") or []) for d in docs)
        elif source == "loans":
            expected = len((docs[0].get("paid") or {})) if docs else 0
        else:
            expected = len(docs)

        resp = client.table(table).select("*", count="exact").limit(1).execute()
        actual = resp.count or 0

        ok = actual >= expected     # >= مش == : صفوف جديدة اتكتبت بعد الاستيراد مش غلط
        mark = "✅" if ok else "❌"
        log(f"  {mark} {table:<24} النسخة={expected:>5}  Supabase={actual:>5}")
        if not ok:
            problems.append(f"{table}: {actual} < {expected}")

    log("")
    if problems:
        log("❌ التحقق فشل:")
        for p in problems:
            log(f"   - {p}")
        return 1
    log("✅ كل الجداول فيها على الأقل عدد النسخة. الاستيراد مؤكد.")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="مسار مجلد النسخة (اللي فيه ملفات الـ json)")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    from services.supabase_service import init_supabase
    import services.supabase_service as sb

    if not init_supabase():
        log("❌ مش قادر أتصل بـ Supabase")
        return 1
    client = sb.supabase_client

    if args.verify:
        return run_verify(client, args.dir)

    log(f"📥 استيراد من: {args.dir}")
    log("")
    for source, table, importer in IMPORTERS:
        docs = load(args.dir, source)
        try:
            count = importer(client, docs)
            log(f"  ✅ {source:<20} -> {table:<24} {count} صف")
        except TransformError as e:
            log(f"  ❌ {source}: قيمة مش قابلة للتحويل -- وقفنا: {e}")
            return 1
        except Exception as e:
            log(f"  ❌ {source}: فشل -- {str(e)[:150]}")
            return 1

    log("")
    log("✅ الاستيراد خلص. شغّل --verify للتأكيد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
