# -*- coding: utf-8 -*-
"""
📋 خدمة استبيانات العملاء (client_briefs)

الجانب القاري لصندوق البريد اللي بتكتب فيه صفحة الاستبيان العامة
(bahr-os-hosting/public/brief.html → جدول client_briefs، ميجريشن 004).

الصفحة بتبعت **لقطات** insert-only: صف جديد مع كل خطوة (is_final=false)
وصف أخير عند الإرسال (is_final=true). فالقراءة هنا دايمًا:
أحدث لقطة لكل session_id، مع تفضيل النهائية على المرحلية.

العقد (نفس عقد supabase_store):
  - قراءة: قيمة عند النجاح، None عند أي فشل أو غياب اتصال
    (None = "مش قادر أجاوب"، مش "مفيش استبيانات").
  - كتابة (تحديث status): True عند النجاح، False عند الفشل.
"""

from datetime import datetime, timezone

from utils.logger import logger
from services import supabase_service

CLIENT_BRIEFS_TABLE = "client_briefs"

# ترتيب عرض الإجابات في التجهيزة -- نفس ترتيب الاستمارة نفسها
_ANSWERS_ORDER = [
    "الاسم", "الموبايل", "مكان الوحدة", "مين بيجاوب", "نوع الوحدة",
    "حالة الوحدة", "الخدمة",
    "الميزانية", "شمول الميزانية", "أولوية التضحية",
    "ممنوعات", "ممنوعات إضافية",
    "فاتح ولا غامق", "ترابي ولا محايد", "هادي ولا جريء",
    "مودرن ولا دافي كلاسيك", "البالتة",
    "عدد الأفراد", "أطفال", "تفاصيل الأطفال", "احتياج أوضة الأطفال",
    "شغل من البيت", "تفاصيل المكتب", "حيوانات", "احتياجات خاصة",
    "تفاصيل الاحتياجات", "بعد ٥ سنين",
    "شكل العزومة", "عدد العزومة", "عزومات رمضان", "نور الصبح",
    "ريحة الأكل", "النضافة", "عفش قديم", "تفاصيل العفش", "أماكن التلفزيون",
    "مقاس السرير", "الدولاب", "المطبخ مفتوح", "الطباخ", "طول الطباخ",
    "أجهزة المطبخ", "مكان الغسالة", "الحمام", "ركن صلاة", "السترة",
    "أول إحساس", "نفسنا في",
]


def _client():
    return supabase_service.supabase_client


def _dedupe_latest(rows):
    """أحدث لقطة لكل جلسة، والنهائية بتكسب المرحلية الأحدث منها.

    الصفوف جاية مرتبة created_at تنازليًا. صف من غير session_id
    (نظريًا مش المفروض يحصل) بيتعامل كجلسة لوحده.
    """
    best = {}
    order = []
    for i, row in enumerate(rows):
        key = row.get("session_id") or f"__no_session_{i}"
        cur = best.get(key)
        if cur is None:
            best[key] = row
            order.append(key)
        elif row.get("is_final") and not cur.get("is_final"):
            # لقطة نهائية أقدم من مرحلية أحدث: النهائية هي المعتمدة،
            # بس المرحلية الأحدث ممكن تحمل تعديل بعد الإرسال -- ناخد
            # النهائية وخلاص (السلوك الحالي للصفحة مبيسمحش بده أصلًا).
            best[key] = row
    return [best[k] for k in order]


def list_new_briefs(limit=200):
    """الاستبيانات اللي لسه متشافتش: أحدث لقطة لكل جلسة.

    بترجع قايمة صفوف (ممكن تكون فاضية) أو None عند الفشل.
    """
    if _client() is None:
        return None
    try:
        resp = (
            _client().table(CLIENT_BRIEFS_TABLE)
            .select("*")
            .eq("status", "new")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return _dedupe_latest(resp.data or [])
    except Exception as e:
        logger.error(f"❌ [client_briefs] فشل جلب الاستبيانات الجديدة: {e}")
        return None


def link_session_to_project(session_id, project_id):
    """يوسم كل لقطات الجلسة بمعرّف مشروع BAHR OS.

    **آدم مش بيعمل المشروع** -- بيربط ببروجيكت موجود اتعمل في BAHR OS
    (قرار أحمد 2026-08-09). الدالة دي بتوسم بس؛ التحقق إن المشروع موجود
    فعلًا مسؤولية المنادي، عشان الطبقة دي تفضل Supabase صافية زي باقي
    الملف (صفر استيراد من firebase_service).
    """
    if _client() is None or not session_id or not project_id:
        return False
    try:
        (
            _client().table(CLIENT_BRIEFS_TABLE)
            .update({"project_id": project_id})
            .eq("session_id", session_id)
            .execute()
        )
        return True
    except Exception as e:
        logger.error(f"❌ [client_briefs] فشل ربط الجلسة {session_id} بمشروع: {e}")
        return False


def list_unlinked_briefs(limit=200):
    """البريفات المكتملة اللي لسه مش مربوطة بمشروع.

    بترجع قايمة (ممكن فاضية) أو None عند الفشل -- نفس عقد باقي القراءات.
    """
    if _client() is None:
        return None
    try:
        resp = (
            _client().table(CLIENT_BRIEFS_TABLE)
            .select("*")
            .is_("project_id", "null")
            .eq("is_final", True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return _dedupe_latest(resp.data or [])
    except Exception as e:
        logger.error(f"❌ [client_briefs] فشل جلب البريفات غير المربوطة: {e}")
        return None


def mark_session_seen(session_id):
    """تعليم كل لقطات الجلسة seen عشان متطلعش تاني في الجديد."""
    if _client() is None or not session_id:
        return False
    try:
        (
            _client().table(CLIENT_BRIEFS_TABLE)
            .update({"status": "seen"})
            .eq("session_id", session_id)
            .eq("status", "new")
            .execute()
        )
        return True
    except Exception as e:
        logger.error(f"❌ [client_briefs] فشل تعليم الجلسة {session_id}: {e}")
        return False


def _fmt_value(value):
    if isinstance(value, list):
        return "، ".join(str(v) for v in value)
    return str(value)


def format_brief(row):
    """صف استبيان -> تجهيزة نصية لتليجرام.

    مش سرد كل الإجابات: العناوين المهمة الأول (مين/فين/ميزانية/عزومة/ممنوعات)
    وبعدين الباقي بترتيب الاستمارة. اللقطة المرحلية بتتعلم صراحةً --
    "وقف عند النص" معلومة، مش عيب نداريه.
    """
    answers = row.get("answers") or {}
    lines = []

    name = row.get("client_name") or answers.get("الاسم") or "من غير اسم"
    phone = row.get("phone") or answers.get("الموبايل") or "من غير رقم"
    where = row.get("unit_location") or answers.get("مكان الوحدة") or ""

    head = f"👤 {name} · {phone}"
    if where:
        head += f" · {where}"
    lines.append(head)

    if not row.get("is_final"):
        answered = len([k for k in answers if answers[k] not in ("", [], None)])
        lines.append(f"⏸️ وقف في النص ({answered} إجابة) — ينفع مكالمة تكمّل الباقي")

    created = row.get("created_at")
    if created:
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            lines.append(f"🕐 {dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
        except Exception:
            pass

    # الأهم الأول
    for key, icon in (
        ("الميزانية", "💰"), ("شمول الميزانية", "💰"),
        ("شكل العزومة", "🍽️"), ("عدد العزومة", "🍽️"),
        ("ممنوعات", "🚫"), ("ممنوعات إضافية", "🚫"),
    ):
        if answers.get(key) not in (None, "", []):
            lines.append(f"{icon} {key}: {_fmt_value(answers[key])}")

    shown = {"الاسم", "الموبايل", "مكان الوحدة",
             "الميزانية", "شمول الميزانية", "شكل العزومة", "عدد العزومة",
             "ممنوعات", "ممنوعات إضافية"}
    rest = [
        f"• {key}: {_fmt_value(answers[key])}"
        for key in _ANSWERS_ORDER
        if key not in shown and answers.get(key) not in (None, "", [])
    ]
    if rest:
        lines.append("—" * 12)
        lines.extend(rest)

    return "\n".join(lines)
