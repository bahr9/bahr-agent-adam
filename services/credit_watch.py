# -*- coding: utf-8 -*-
"""
💳 مراقبة رصيد Anthropic -- تنبيه قبل ما يخلص، مش بعد.

## ليه

يوم 2026-08-15 الرصيد خلص في نص شغل. آدم بقى مش قادر يرد على أي رسالة --
كل رد نصي بيعدي على Claude ومفيش مزوّد بديل -- وأحمد اكتشف ده من رد فاشل،
مش من تنبيه. وقبلها بتسعة أيام حصل نفس الشيء (2026-08-06)، وهي الحادثة
اللي اتعمل عشانها جدول `api_usage` أصلاً.

الجدول ده بيسجل كل نداء بتوكناته من ساعتها. اللي كان ناقص هو القراءة.

## اللي مفيش طريقة نعرفه

**مفيش أي API عند Anthropic بيقول الرصيد المتبقي.** فيه تقارير استهلاك
(Admin API بمفتاح إداري منفصل) بس مفيش "فاضل كام". فالحساب هنا:

    المتبقي = اللي أحمد شحنه  -  اللي اتصرف من ساعة الشحن

يعني بيعتمد على إن أحمد يقول قيمة الشحن (`/credit 25`). من غيرها مفيش
تنبيه استباقي -- بس التنبيه الفوري عند نفاد الرصيد بيفضل شغال.

## دقة الأسعار

الأسعار مكتوبة تحت وبتتغير من Anthropic من وقت للتاني. لو اتغيّرت،
التقدير هيبقى غلط -- عشان كده الرسالة بتقول "تقديري" مش رقم قاطع، وبتقول
المصروف المقيس جنب المتبقي عشان أحمد يقارن بصفحة الفواتير لو حب.
"""

from utils.logger import logger

FLAG_DOC = "anthropic_credit"

# $ لكل مليون توكن: (دخل، خرج، قراءة كاش، كتابة كاش)
# كتابة الكاش هنا بسعر الساعة (2×) مش الخمس دقايق (1.25×)، لأن
# `_tracked_create` بيبعت هيدر extended-cache-ttl على كل نداء.
RATES = {
    "claude-sonnet-5":           (3.00, 15.00, 0.30, 6.00),
    "claude-opus-5":             (5.00, 25.00, 0.50, 10.00),
    "claude-haiku-4-5-20251001": (1.00,  5.00, 0.10,  2.00),
    "claude-haiku-4-5":          (1.00,  5.00, 0.10,  2.00),
}
_DEFAULT_RATE = RATES["claude-sonnet-5"]

# نسب التنبيه. مرة واحدة لكل نسبة -- مش كل فحص.
THRESHOLDS = (0.80, 0.95)


def _flags():
    from services.firebase_service import firestore_db
    return firestore_db.collection("system_flags").document(FLAG_DOC) if firestore_db else None


def record_topup(amount_usd, at_iso=None):
    """يسجّل شحنة جديدة ويصفّر التنبيهات المرسلة.

    بيرجع (ok, رسالة).
    """
    try:
        amount = float(amount_usd)
    except (TypeError, ValueError):
        return False, "المبلغ لازم يكون رقم بالدولار."
    if amount <= 0:
        return False, "المبلغ لازم يكون أكبر من صفر."

    ref = _flags()
    if ref is None:
        return False, "مش قادر أوصل للتخزين دلوقتي -- مسجلتش الشحنة."

    from utils.time_utils import now_cairo
    at = at_iso or now_cairo().isoformat()
    try:
        ref.set({"amount_usd": amount, "at": at, "alerted": []})
        logger.info(f"💳 شحنة اتسجلت: ${amount} في {at}")
        return True, f"سجّلت شحنة ${amount:g}. هحسب المصروف من دلوقتي وأنبّهك عند 80% و95%."
    except Exception as e:
        logger.error(f"❌ فشل تسجيل الشحنة: {e}")
        return False, str(e)[:120]


def _cost_of(row):
    ri, ro, rr, rw = RATES.get(row.get("model") or "", _DEFAULT_RATE)
    return (
        (row.get("input_tokens") or 0) / 1e6 * ri
        + (row.get("output_tokens") or 0) / 1e6 * ro
        + (row.get("cache_read_tokens") or 0) / 1e6 * rr
        + (row.get("cache_write_tokens") or 0) / 1e6 * rw
    )


def spend_since(at_iso):
    """المصروف بالدولار من التاريخ ده. None لو مقدرناش نقرا.

    None مش صفر: لو `api_usage` مش قابل للقراءة، الرد الصح "مش عارف"
    مش "مصرفتش حاجة" -- والتاني بيدي طمأنينة كاذبة بالظبط في اللحظة
    اللي المفروض ننبّه فيها.
    """
    from services import supabase_store
    client = supabase_store._client()
    if client is None:
        return None
    total, page = 0.0, 0
    try:
        while page < 30:                       # سقف صفحات، مش سقف صامت
            resp = (
                client.table("api_usage")
                .select("model, input_tokens, output_tokens, "
                        "cache_read_tokens, cache_write_tokens")
                .gte("at", at_iso)
                .range(page * 1000, page * 1000 + 999)
                .execute()
            )
            rows = resp.data or []
            total += sum(_cost_of(r) for r in rows)
            if len(rows) < 1000:
                return round(total, 4)
            page += 1
        logger.warning("⚠️ [credit] وصلت سقف الصفحات -- المصروف المحسوب أقل من الحقيقي")
        return round(total, 4)
    except Exception as e:
        logger.error(f"❌ [credit] قراءة api_usage فشلت: {e}")
        return None


def status():
    """{'ok': bool, 'reason'|('amount','spent','remaining','pct')}"""
    ref = _flags()
    if ref is None:
        return {"ok": False, "reason": "التخزين مش متاح"}
    try:
        doc = ref.get()
    except Exception as e:
        return {"ok": False, "reason": f"قراءة العلامة فشلت: {str(e)[:60]}"}
    if not doc.exists:
        return {"ok": False, "reason": "مفيش شحنة مسجّلة -- استخدم /credit <المبلغ>"}

    data = doc.to_dict() or {}
    amount = float(data.get("amount_usd") or 0)
    spent = spend_since(data.get("at") or "")
    if spent is None:
        return {"ok": False, "reason": "مقدرتش أقرا سجل الاستهلاك -- مش عارف المصروف"}

    remaining = amount - spent
    return {
        "ok": True,
        "amount": amount,
        "spent": spent,
        "remaining": remaining,
        "pct": (spent / amount) if amount else 1.0,
        "at": data.get("at"),
        "alerted": list(data.get("alerted") or []),
    }


def check_and_alert(send):
    """يفحص ويبعت تنبيه مرة واحدة لكل نسبة. `send(text)` بتبعت لأحمد.

    بيرجع النص المبعوت أو None.
    """
    st = status()
    if not st.get("ok"):
        return None

    crossed = [t for t in THRESHOLDS if st["pct"] >= t and t not in st["alerted"]]
    if not crossed:
        return None
    top = max(crossed)

    msg = (
        f"💳 رصيد Anthropic: صرفت ${st['spent']:.2f} من ${st['amount']:.2f} "
        f"({st['pct']*100:.0f}%). فاضل تقديريًا **${st['remaining']:.2f}**.\n\n"
        "الرقم تقديري -- محسوب من توكنات النداءات المسجّلة بأسعار مكتوبة عندي، "
        "مش من Anthropic نفسها (مفيش API بيقول الرصيد). "
        "لو خلص، مش هقدر أرد على أي رسالة خالص."
    )
    try:
        send(msg)
    except Exception as e:
        logger.error(f"❌ [credit] فشل إرسال التنبيه: {e}")
        return None

    try:
        _flags().set({"alerted": sorted(set(st["alerted"]) | {top})}, merge=True)
    except Exception as e:
        # التنبيه اتبعت بس العلامة مااتسجلتش -- هيتكرر. مزعج، مش خطر،
        # وأحسن من إننا نبلع التنبيه.
        logger.warning(f"⚠️ [credit] التنبيه اتبعت والعلامة مااتحفظتش: {e}")
    logger.info(f"💳 تنبيه رصيد اتبعت عند {top*100:.0f}%")
    return msg


# ============================================================
# التنبيه الفوري عند نفاد الرصيد
# ============================================================

_EXHAUSTED_MARKERS = ("credit balance is too low", "insufficient_quota",
                      "billing", "Plans & Billing")


def is_credit_exhausted(error) -> bool:
    """الخطأ ده معناه الرصيد خلص؟

    الرسالة اللي Anthropic بتبعتها: 400 invalid_request_error --
    "Your credit balance is too low to access the Anthropic API."
    من غير الفحص ده، أحمد بياخد "❌ حصلت مشكلة" -- رسالة مبتقولش السبب
    ولا الحل، فبيفضل يجرب.
    """
    text = str(error or "")
    return any(m.lower() in text.lower() for m in _EXHAUSTED_MARKERS)


EXHAUSTED_MESSAGE = (
    "💳 **رصيد Anthropic خلص** -- مش قادر أرد على أي حاجة لحد ما تشحن.\n\n"
    "كل رد عندي بيعدي على Claude ومفيش مزوّد بديل. اللي لسه شغال من غيره: "
    "التذكيرات العادية والباكب. اللي واقف: أي رد، بريف الصبح، والتذكيرات المتكررة."
)
