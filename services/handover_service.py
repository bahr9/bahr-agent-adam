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


STAGES = (
    ("brief", "الاستبيان"),
    ("direction", "الاتجاه"),
    ("proposal", "العرض الأول"),
    ("handover", "التسليم"),
)


def _approvals_section(approvals):
    """كل مرحلة بمستند معتمد (أحمد 2026-08-10).

    ده تسجيل مش قفل: البوابة بتسعّر الاختصار مبتقفلوش (تصور §2.4).
    المرحلة اللي عدّت من غير اعتماد بتتقال بالاسم -- عشان الاختصار
    يبقى قرار مكتوب، مش حاجة اكتشفناها بعد سنة.
    """
    done = {}
    for a in approvals or []:
        st = (a or {}).get("stage")
        if st:
            done[st] = a

    out = ["\n🖊 الاعتمادات:"]
    missing = []
    for key, label in STAGES:
        a = done.get(key)
        if a:
            how = (a.get("how") or "").strip()
            line = "✅ " + label
            if how:
                line += " — " + how
            at = a.get("at")
            if at:
                line += " · " + str(at)[:10]
            out.append(line)
        else:
            out.append("○ " + label + " — مفيش اعتماد متسجل")
            missing.append(label)

    if missing:
        out.append("\n⚠️ " + "، ".join(missing) +
                   ": عدّت من غير توقيع. لو الخلاف قام، مفيش سطر يحسمه.")
    return out


def _objections_section(objections):
    """رد العميل على العرض -- اللي اعترض عليه واللي عملناه.

    المفتوح بيتعلّم: المحضر اللي فيه اعتراض من غير رد مش محضر تسليم،
    ده شغل لسه شغال.
    """
    if not objections:
        return []

    open_ones = [o for o in objections if not (o.get("did") or "").strip()]
    out = ["\n🗣 رد العميل على العرض — " + str(len(objections)) + ":"]
    for o in objections:
        out.append("\n• «" + (o.get("said") or "") + "»")
        did = (o.get("did") or "").strip()
        out.append("   ↳ " + (did if did else "⏳ لسه مردّيناش"))
        at = o.get("at")
        if at:
            out.append("   بتاريخ: " + str(at)[:10])
    if open_ones:
        out.append("\n⚠️ فيه " + str(len(open_ones)) +
                   " اعتراض من غير رد — المشروع مايتقفلش وهو مفتوح.")
    return out


def format_handover(row):
    """المحضر: اللي اتكسر ومين وافق، ورد العميل على العرض."""
    a = (row or {}).get("answers") or {}
    name = (row or {}).get("client_name") or a.get("الاسم") or "من غير اسم"
    waivers = (row or {}).get("waivers") or []
    objections = (row or {}).get("objections") or []

    out = ["📋 محضر التسليم — " + name]
    pid = (row or {}).get("project_id")
    out.append("المشروع: " + (pid if pid else "مش مربوط بمشروع لسه"))

    if not waivers:
        out.append("\n✅ مفيش قاعدة اتكسرت — التنفيذ ماشي على التوقيع بالكامل.")
    else:
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

    out.extend(_objections_section(objections))
    out.extend(_approvals_section((row or {}).get("approvals") or []))

    if waivers or objections:
        out.append("\nالسطور دي بتحمي الطرفين — مش اتهام لحد.")
    return "\n".join(out)
