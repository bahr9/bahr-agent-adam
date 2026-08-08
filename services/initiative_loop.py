# -*- coding: utf-8 -*-
"""
🔁 حلقة المبادرة -- آدم قال، وأحمد رد ولا لأ؟

الفجوة اللي الملف ده بيسدها (تشخيص 2026-08-08، الفجوة رقم ٢): مسار الـ
Active اتجاه واحد. آدم بيبادر، وأحمد بيرد، ومفيش حاجة بتربط الرد بالحاجة
اللي آدم اتكلم عنها. فبعد أسبوع آدم مش عارف إنه اتكلم أصلًا ولا إيه اللي
حصل بعدها.

**قراءة بس -- صفر لمس لمسار تليجرام.**

ودي مش رفاهية في التصميم، دي كانت الشرط: الطرف الراجع هو رسايل أحمد، وأول
فكرة كانت خطّاف في `handle_message`. اتضح إنه مش لازم -- الطرفين متسجلين
بأوقاتهم خلاص:

  - `expressions` (Firestore): expression_id · dimension · mode · sent_at
  - `conversation_messages` (Supabase): user_text · occurred_at

فالوصلة بتتحسب من بيانات موجودة، ومفيش مسار كتابة جديد ينفع يقع، ومستحيل
حاجة هنا تأخر رد أحمد أو تكسره.

**القيد الصادق:** الربط **زمني مش دلالي**. "أحمد بعت رسالة بعد المبادرة"
مش نفس "أحمد رد على المبادرة" -- ممكن يكون بيتكلم في حاجة تانية خالص.
الدالة بترجع النص عشان تحكم بنفسك، وعمرها ما بتدّعي إنها فهمت النية.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from config import EXPRESSIONS_COLLECTION
from utils.logger import logger

# أوسع نافذة رد بنقيسها أيام، فآخر بضع مئات من الرسايل بتغطيها بفارق أمان
# كبير. الرقم موجود كسقف مش كاختيار دلالي.
MAX_MESSAGES_SCANNED = 1500

# بعد قد إيه نعتبر الرسالة مش رد على المبادرة. اليوم اختيار محافظ: أبعد من
# كده والربط الزمني بيبقى ضعيف لدرجة إنه يضلل أكتر ما يفيد.
RESPONSE_WINDOW_HOURS = 24


def _parse(ts) -> Optional[datetime]:
    """وقت ISO -> datetime واعي بالمنطقة. None معناها مش مقروء -- مش دلوقتي.

    الجانبين بيكتبوا بمناطق مختلفة (المبادرات بتوقيت القاهرة، المحادثات
    UTC)، والاتنين واعيين بالمنطقة فالمقارنة بينهم سليمة. أي وقت ساذج
    بنعتبره UTC بدل ما نرمي استثناء.
    """
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _load_initiatives():
    """المبادرات المرسلة فعلًا (mode بيبدأ بـ active)، مرتبة زمنيًا."""
    from services.firebase_service import firestore_db
    if firestore_db is None:
        logger.warning("🔁 حلقة المبادرة: Firestore مش متصل -- مفيش مبادرات")
        return []
    try:
        docs = [d.to_dict() for d in firestore_db.collection(EXPRESSIONS_COLLECTION).stream()]
    except Exception as e:
        logger.error(f"🔁 حلقة المبادرة: قراءة التعبيرات فشلت: {str(e)[:90]}")
        return []

    out = []
    for d in docs or []:
        if not str(d.get("mode") or "").startswith("active"):
            continue
        when = _parse(d.get("sent_at"))
        if when is None:
            continue          # من غير وقت مفيش ربط -- بنتخطاها مش نخمّنها
        out.append({
            "expression_id": d.get("expression_id"),
            "dimension": d.get("dimension"),
            "mode": d.get("mode"),
            "level": d.get("level"),
            "text": d.get("rendered_text"),
            "sent_at": when,
        })
    out.sort(key=lambda r: r["sent_at"])
    return out


def _load_messages():
    """رسايل أحمد بأوقاتها، مرتبة زمنيًا."""
    from services import supabase_store
    client = supabase_store._client()
    if client is None:
        logger.warning("🔁 حلقة المبادرة: Supabase مش متصل -- مفيش رسايل")
        return []
    try:
        # حد صريح: من غيره ده بيسحب **كل رسالة أحمد بعتها في حياته** بنصها
        # الكامل عشان يحسب بوليان عن نافذة ساعات. وأخطر من الحجم: من غير
        # ORDER BY، أي قص من جهة PostgREST بيبقى عشوائي -- فمبادرة أحمد رد
        # عليها فعلًا ترجع responded=False، وبريف الصبح يتهمه بإنه مردش
        # (مراجعة 2026-08-08).
        rows = (client.table("conversation_messages")
                .select("user_text,occurred_at")
                .order("occurred_at", desc=True)
                .limit(MAX_MESSAGES_SCANNED).execute().data) or []
    except Exception as e:
        logger.error(f"🔁 حلقة المبادرة: قراءة المحادثات فشلت: {str(e)[:90]}")
        return []

    out = []
    for r in rows:
        when = _parse(r.get("occurred_at"))
        if when is None:
            continue
        out.append({"text": r.get("user_text") or "", "at": when})
    out.sort(key=lambda r: r["at"])
    return out


def get_initiative_outcomes(window_hours: int = RESPONSE_WINDOW_HOURS) -> list:
    """لكل مبادرة: أحمد رد؟ بعد قد إيه؟ وقال إيه؟

    بترجع ليستة مرتبة من الأقدم للأحدث، كل عنصر فيه:
      expression_id · dimension · mode · sent_at · responded ·
      latency_minutes (أو None) · response_text (أو None)

    `responded=False` معناها **مفيش رسالة في النافذة** -- وده معلومة حقيقية
    مش نقص بيانات: يعني آدم اتكلم ومحصلش حاجة.
    """
    initiatives = _load_initiatives()
    messages = _load_messages()
    window = timedelta(hours=window_hours)

    results = []
    for ini in initiatives:
        reply = next((m for m in messages
                      if ini["sent_at"] < m["at"] <= ini["sent_at"] + window), None)
        results.append({
            "expression_id": ini["expression_id"],
            "dimension": ini["dimension"],
            "mode": ini["mode"],
            "level": ini["level"],
            "initiative_text": ini["text"],
            "sent_at": ini["sent_at"].isoformat(),
            "responded": reply is not None,
            "latency_minutes": (
                round((reply["at"] - ini["sent_at"]).total_seconds() / 60, 1)
                if reply else None
            ),
            "response_text": reply["text"] if reply else None,
        })
    return results


def summarize(window_hours: int = RESPONSE_WINDOW_HOURS) -> dict:
    """ملخص رقمي للحلقة -- الأساس اللي أي حكم على المبادرة يتبنى عليه.

    `coverage_gap` هو الحقل اللي بيمنع قراءة الأرقام غلط: مبادرات حصلت
    **قبل** ما تخزين المحادثات يبتدي مستحيل يكون ليها رد مسجّل، فعدّها
    كـ"محدش رد" كذب. بتتحسب منفصلة وبتتشال من النسبة.
    """
    outcomes = get_initiative_outcomes(window_hours)
    messages = _load_messages()
    earliest_message = messages[0]["at"] if messages else None

    # الشرط الصح: المبادرة تتشال لو **نافذة الرد بتاعتها كلها** قفلت قبل ما
    # أول رسالة تتسجل. مقارنة sent_at لوحده بأول رسالة غلط -- مبادرة قبل
    # أول رسالة بربع ساعة ممكن تكون الرسالة دي هي ردها بالظبط.
    window = timedelta(hours=window_hours)
    countable, uncountable = [], []
    for o in outcomes:
        sent = _parse(o["sent_at"])
        closed_before_storage = (
            earliest_message is not None
            and sent is not None
            and sent + window < earliest_message
        )
        (uncountable if closed_before_storage else countable).append(o)

    answered = [o for o in countable if o["responded"]]
    lat = sorted(o["latency_minutes"] for o in answered if o["latency_minutes"] is not None)

    return {
        "initiatives_total": len(outcomes),
        "countable": len(countable),
        "coverage_gap": len(uncountable),
        "responded": len(answered),
        "response_rate": (round(100 * len(answered) / len(countable)) if countable else None),
        "median_latency_minutes": (lat[len(lat) // 2] if lat else None),
        "by_dimension": _count_by(outcomes, "dimension"),
        "by_mode": _count_by(outcomes, "mode"),
    }


def _count_by(rows, key):
    out = {}
    for r in rows:
        out[r.get(key)] = out.get(r.get(key), 0) + 1
    return out
