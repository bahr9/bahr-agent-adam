# -*- coding: utf-8 -*-
"""
🧵 خيط الانتباه -- إيه المفتوح، من إمتى، وآدم قال عنه إيه قبل كده؟

الفجوة اللي الملف ده بيسدها (تشخيص 2026-08-08، الفجوة رقم ١): آدم عنده
ذاكرة، مالوش خيط. بيخزّن أحداث ولقطات وتعبيرات -- كل قطعة لوحدها -- ومفيش
حاجة بتربطهم. فمش قادر يجاوب أبسط سؤال بيميز فرد الأسرة عن نظام المراقبة:
**"الحاجة دي مفتوحة من إمتى، وأنا قلت عنها إيه، وحصل إيه بعدها؟"**

فرد الأسرة مش بيتميز بإنه فاكر -- بيتميز بإنه **بيربط**: "إنت قلت هتعملها
من أسبوعين".

بيجمّع تلات مصادر موجودة، **قراءة بس -- صفر كتابة**:

  1. `self_state_engine`  -> إيه المفتوح دلوقتي وبكام
  2. `decision_engine`    -> من إمتى وهو على الحالة دي (`since`)
  3. `initiative_loop`    -> آدم قال عنه إيه آخر مرة، ورد عليه حد ولا لأ

القاعدة اللي بتحكم كل حقل هنا: **مش عارف ≠ صفر.** أي مدة مش محسوبة من
`since` مخزّن بترجع None، والجملة اللي محتاجاها متتقالش. نفس قاعدة الأمانة
اللي بتحكم المساحات والأسعار، مطبّقة على الوقت.
"""

from datetime import datetime, timezone
from typing import Optional

from utils.logger import logger

# الأبعاد اللي "مفتوحة" ليها معنى: مستواها مش none. tracking_stability
# مستبعد عن قصد -- ملاحظة موضوعية محايدة مش حاجة "مفتوحة" محتاجة قفل
# (نفس سبب استبعاده من HIGHEST_TIER في decision_engine).
_NOT_OPEN_LEVELS = {"none"}
_EXCLUDED_DIMENSIONS = {"tracking_stability"}


def _parse(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _days_between(earlier: Optional[datetime], later: datetime) -> Optional[int]:
    """أيام كاملة، أو None لو الوقت مش معروف. None معناها مش عارف."""
    if earlier is None:
        return None
    return max(0, (later - earlier).days)


def get_open_threads() -> list:
    """كل حاجة مفتوحة دلوقتي، ومعاها تاريخها.

    لكل عنصر:
      dimension · level · count
      open_since / days_open        -- من إمتى على الحالة دي (None = مش معروف)
      last_spoken_at / days_since_spoken / last_spoken_text
      spoke_about_it (bool)         -- آدم فتح الموضوع ده قبل كده أصلًا؟
      answered (bool أو None)       -- None لو مفيش كلام يتقاس عليه
      unanswered_days               -- قال ومحدش رد، بقاله كام يوم

    مرتبة بالأقدم مفتوحًا الأول -- اللي قاعد من زمان هو اللي محتاج انتباه.
    """
    now = datetime.now(timezone.utc)

    try:
        from services import self_state_engine
        state = self_state_engine.compute_self_state()
    except Exception as e:
        logger.error(f"🧵 خيط الانتباه: حساب الحالة فشل: {str(e)[:90]}")
        return []

    try:
        from services import decision_engine
        tracked = decision_engine.get_tracked_levels()
    except Exception as e:
        logger.warning(f"🧵 خيط الانتباه: قراءة المدد فشلت -- هيكمل من غير 'من إمتى': {str(e)[:90]}")
        tracked = {}

    try:
        from services import initiative_loop
        outcomes = initiative_loop.get_initiative_outcomes()
    except Exception as e:
        logger.warning(f"🧵 خيط الانتباه: قراءة المبادرات فشلت -- هيكمل من غير تاريخ الكلام: {str(e)[:90]}")
        outcomes = []

    # آخر مبادرة لكل بُعد
    latest = {}
    for o in outcomes:
        dim = o.get("dimension")
        when = _parse(o.get("sent_at"))
        if dim is None or when is None:
            continue
        if dim not in latest or when > latest[dim]["_when"]:
            latest[dim] = {**o, "_when": when}

    threads = []
    for dim, dim_state in state.items():
        if dim in _EXCLUDED_DIMENSIONS or not isinstance(dim_state, dict):
            continue
        level = dim_state.get("level")
        if level in _NOT_OPEN_LEVELS or level is None:
            continue

        since = _parse((tracked.get(dim) or {}).get("since"))
        spoken = latest.get(dim)
        spoken_at = spoken["_when"] if spoken else None
        days_since_spoken = _days_between(spoken_at, now)
        answered = spoken.get("responded") if spoken else None

        threads.append({
            "dimension": dim,
            "level": level,
            "count": dim_state.get("count"),
            "open_since": since.isoformat() if since else None,
            "days_open": _days_between(since, now),
            "spoke_about_it": spoken is not None,
            "last_spoken_at": spoken_at.isoformat() if spoken_at else None,
            "days_since_spoken": days_since_spoken,
            "last_spoken_text": spoken.get("initiative_text") if spoken else None,
            "answered": answered,
            # قال ومحدش رد وبقاله كام يوم -- ده اللي بيفرّق بين "بلّغ" و"بيتابع"
            "unanswered_days": (
                days_since_spoken if (spoken is not None and answered is False) else None
            ),
        })

    # الأقدم مفتوحًا الأول؛ اللي مدته مجهولة في الآخر (مش الأول -- عشان
    # مايتصدرش الترتيب بناءً على معلومة إحنا مش عارفينها)
    threads.sort(key=lambda t: (t["days_open"] is None, -(t["days_open"] or 0)))
    return threads


def describe_open_threads() -> str:
    """نص عربي للخيط -- كل جملة فيه مبنية على حقل متحقق.

    أي مدة مش معروفة **بتتشال من الجملة** بدل ما تتقدّر. النتيجة أقصر
    وأصدق: "فيه 3 تعارضات معلّقة" أأمن من "فيه 3 تعارضات من 7 أيام" لما
    السبعة دي تخمين.
    """
    threads = get_open_threads()
    if not threads:
        return "مفيش حاجة مفتوحة محتاجة متابعة دلوقتي."

    lines = []
    for t in threads:
        count = t.get("count")
        head = f"{t['dimension']}: {count}" if count is not None else t["dimension"]
        if t["days_open"] is not None:
            head += f" — مفتوحة من {t['days_open']} يوم"

        if not t["spoke_about_it"]:
            head += " — ومقلتش عنها حاجة لسه"
        elif t["answered"] is False and t["unanswered_days"] is not None:
            head += f" — قلت عنها من {t['unanswered_days']} يوم ومحصلش رد"
        elif t["answered"] is True:
            head += " — قلت عنها وأحمد رد"
        elif t["days_since_spoken"] is not None:
            head += f" — قلت عنها من {t['days_since_spoken']} يوم"
        else:
            head += " — قلت عنها قبل كده"

        lines.append("- " + head)

    return "\n".join(lines)
