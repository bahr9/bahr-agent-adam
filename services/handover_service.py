# -*- coding: utf-8 -*-
"""
📋 محضر التسليم -- سجل اللي اتكسر ومين وافق

قاعدة أحمد (2026-08-10): "أي قاعدة اتكسرت بطلب العميل تتسجل في محضر
التسليم: مين اقترح ومين وافق".

القاعدة دي مكانتش ليها مكان تتسجل فيه، فكانت مكتوبة ومش شغالة. المحضر
هنا هو مكانها.

## ليه التسجيل تلقائي

`/direction` بيحسب التنازلات أصلًا. لو خلّينا التسجيل خطوة يدوية، هينتسي
في أول يوم مزحوم -- والقاعدة اللي بتنتسي مالهاش لازمة. فالتنازل بيتسجل
لحظة ما يحصل، وأحمد بيراجع مش بيدخّل.

## الحماية اللي بيوفرها

بعد سنة، "انت اللي اخترت الاستانلس" مش نقاش -- ده سطر بتاريخه مكتوب فيه
إن أحمد اقترح النحاس والعميل هو اللي منع اللامع.
"""

from datetime import datetime, timezone

from utils.logger import logger
from services import supabase_service

TABLE = "client_briefs"


def _client():
    return supabase_service.supabase_client


def _key(w):
    """هوية التنازل -- القاعدة + اللي اتنزل عنه. بتمنع التكرار مع كل تشغيلة."""
    return (w.get("rule") or "", w.get("gave_up") or "")


def merge_waivers(existing, yields):
    """تنازلات جديدة فوق القديمة، من غير تكرار.

    بترجع (القايمة الكاملة، عدد الجديد) -- المنادي بيكتب لو فيه جديد بس.
    """
    out = list(existing or [])
    seen = {_key(w) for w in out}
    added = 0
    now = datetime.now(timezone.utc).isoformat()
    for y in yields or []:
        w = {
            "rule": y.get("rule_id") or "",
            "text": y.get("rule") or "",
            "gave_up": y.get("material") or "",
            "because": y.get("ban") or "",
            "proposed_by": "أحمد",
            "agreed_by": "العميل",
            "at": now,
        }
        if _key(w) in seen:
            continue
        seen.add(_key(w))
        out.append(w)
        added += 1
    return out, added


def record_yields(session_id, existing, yields):
    """يسجل التنازلات على البريف. بيرجع عدد اللي اتسجل، أو 0.

    بيفشل بصمت عن قصد: التسجيل مايوقفش عرض الاتجاه.
    """
    if _client() is None or not session_id or not yields:
        return 0
    merged, added = merge_waivers(existing, yields)
    if not added:
        return 0
    try:
        (_client().table(TABLE).update({"waivers": merged})
         .eq("session_id", session_id).execute())
        return added
    except Exception as e:
        logger.error(f"❌ [handover] فشل تسجيل التنازلات: {e}")
        return 0


def format_handover(row):
    """المحضر: اللي اتكسر ومين وافق، والأرقام."""
    a = (row or {}).get("answers") or {}
    name = (row or {}).get("client_name") or a.get("الاسم") or "من غير اسم"
    waivers = (row or {}).get("waivers") or []

    out = ["📋 محضر التسليم — " + name]
    pid = (row or {}).get("project_id")
    out.append("المشروع: " + (pid if pid else "مش مربوط بمشروع لسه"))

    if not waivers:
        out.append("\n✅ مفيش قاعدة اتكسرت — التنفيذ ماشي على التوقيع بالكامل.")
        return "\n".join(out)

    out.append("\n🤝 قواعد اتكسرت بطلب العميل — " + str(len(waivers)) + ":")
    for w in waivers:
        out.append("\n• " + (w.get("text") or w.get("rule") or "قاعدة"))
        if w.get("gave_up"):
            out.append("   اتنزل عن: " + w["gave_up"])
        if w.get("because"):
            out.append("   السبب: " + w["because"])
        out.append("   اقترحها: " + (w.get("proposed_by") or "—") +
                   " · وافق: " + (w.get("agreed_by") or "—"))
        at = w.get("at")
        if at:
            out.append("   بتاريخ: " + str(at)[:10])

    out.append("\nالسطور دي بتحمي الطرفين — مش اتهام لحد.")
    return "\n".join(out)
