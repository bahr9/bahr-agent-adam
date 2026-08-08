# -*- coding: utf-8 -*-
"""
🎯 Decision Engine -- ADAM Self-State & Observation System (Stage 5, v0.1)
=====================================================
الطبقة التالتة: بتقرر هل بُعد معيّن من الـ Self-State يستاهل يتقال دلوقتي
(Active) ولا بس لو حد سأل (Passive).

قاعدة معتمدة من أحمد (2026-07-24): Active بس لما بُعد يوصل لأعلى مستوى
بتاعه *لأول مرة* (انتقال حقيقي، مش استمرار). لو آدم بلّغ عن الحالة قبل
كده ومفيش تغيير، مبيكررش التبليغ.

التخزين: أصغر أثر ممكن -- "آخر مستوى اتلاحظ لكل بُعد" بس، في
config.SELF_STATE_COLLECTION. دي الحاجة الوحيدة اللي محتاجة تتخزن في كل
المعمارية (Self-State نفسها بتتحسب فريش من self_state_engine، مش متخزنة).

نطاق Stage 5: القرار (Active/Passive) بس. الصياغة الفعلية وإرسالها لأحمد
هو صلب Expression layer (مراحل 6/7 -- لسه مش متبنية). مفيش حد بينادي
الدالة دي فعليًا لسه في مسار التشغيل العادي -- بنية جاهزة للمراحل الجاية.
"""

from config import SELF_STATE_COLLECTION
from utils.logger import logger

_DOC_ID = "decision_engine_state"

# أعلى مستوى لكل بُعد -- زي ما اتعرّف في self_state_engine.py
#
# ملحوظة مقصودة: tracking_stability (Stage 5.1) مش موجود هنا عمدًا.
# "frequent_corrections" ملاحظة موضوعية محايدة مش "مشكلة" (التصحيح الموثّق
# سلوك حوكمة صحي) -- فمش من النوع اللي يستاهل آدم يبادر بيه (Active). بيفضل
# Passive دايمًا: يتقال بس لو حد سأل، زي أي بُعد تاني في مستواه الطبيعي.
HIGHEST_TIER = {
    "unresolved_conflict": "high",
    "pending_obligation_load": "concern",
}

# كام يوم ثبات تام على أسوأ درجة يعتبر "متسابة" مش "مستقرة".
#
# الرقم ده هو الحد الوحيد اللي بيقرر إمتى آدم يرجع يتكلم عن حاجة قال عنها
# قبل كده. لو صغير أوي بيبقى زن، لو كبير أوي بيبقى إهمال. أحمد قال "زي
# أسبوع" كمثال -- متحطّش هنا كرقم نهائي، وده المكان الوحيد اللي بيتغير منه.
STALE_DAYS = 7


def _normalize_record(raw):
    """قراءة سجل بُعد واحد بالشكل الجديد، مع احترام الشكل القديم.

    الشكل القديم كان نص واحد بس ("high"). البيانات دي **موجودة فعلًا في
    الإنتاج**، فقراءتها لازم تعدي من غير كسر -- بترجع بمستوى معروف وعدد
    ووقت مجهولين، وده بالظبط اللي المفروض يحصل: مش عارفين، مش بنخترع.
    """
    if isinstance(raw, str):
        return {"level": raw, "count": None, "since": None}
    if isinstance(raw, dict):
        return {
            "level": raw.get("level"),
            "count": raw.get("count"),
            "since": raw.get("since"),
        }
    return {"level": None, "count": None, "since": None}


def _days_since(since_iso):
    """عدد الأيام الكاملة من `since` -- أو None لو مش متسجل/مش مقروء.

    None هنا معناها "مش عارف"، ومحدش مسموح له يحوّلها لرقم. القاعدة اللي
    بتحكم المساحات والأسعار بتحكم الوقت بنفس الصرامة: لو `since` مش موجود،
    الجملة اللي محتاجة رقم أيام **متتقالش** أصلًا.
    """
    if not since_iso:
        return None
    try:
        from datetime import datetime, timezone

        parsed = datetime.fromisoformat(str(since_iso).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - parsed).days)
    except Exception as e:
        logger.warning(f"⚠️ since مش مقروء ({since_iso!r}) -- بنتعامل معاه كمجهول: {e}")
        return None


def _get_last_levels() -> dict:
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return {}
    try:
        doc = firestore_db.collection(SELF_STATE_COLLECTION).document(_DOC_ID).get()
        return doc.to_dict().get("last_levels", {}) if doc.exists else {}
    except Exception as e:
        logger.error(f"❌ خطأ في جلب last_levels: {e}")
        return {}


def _save_last_levels(levels: dict):
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return
    try:
        firestore_db.collection(SELF_STATE_COLLECTION).document(_DOC_ID).set(
            {"last_levels": levels}, merge=True
        )
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ last_levels: {e}")


def decide_expression(self_state: dict) -> dict:
    """
    لكل بُعد في self_state (ناتج self_state_engine.compute_self_state):
    يقرر mode="active" لو وصل لأعلى مستوى بتاعه *لأول مرة* (transition من
    مستوى مختلف)، وإلا "passive". بيحدّث "آخر مستوى ملاحظ" كجزء أساسي من
    عمل الدالة (مش أثر جانبي عرضي) -- ده اللي بيمنع تكرار التبليغ، وده
    اللي بيخلي انتقال جديد (لو المستوى نزل وبعدين رجع طلع تاني) يتلاحظ صح.
    """
    from utils.time_utils import now_cairo

    last_levels = _get_last_levels()
    decisions = {}
    updated_levels = dict(last_levels)
    now_iso = now_cairo().isoformat()

    for dimension, highest in HIGHEST_TIER.items():
        dim_state = self_state.get(dimension)
        if not dim_state:
            continue

        current_level = dim_state["level"]
        current_count = dim_state.get("count")
        previous = _normalize_record(last_levels.get(dimension))
        previous_level = previous["level"]

        at_worst = current_level == highest
        days = None

        if at_worst and previous_level != highest:
            # وصل لأسوأ درجة لأول مرة -- السلوك الأصلي زي ما هو، والساعة تبدأ
            mode = "active"
            since = now_iso
        elif at_worst:
            # قاعد على أسوأ درجة. سببين بس يخلوه يتكلم تاني:
            elapsed = _days_since(previous["since"])
            count_moved = (
                current_count is not None
                and previous["count"] is not None
                and current_count != previous["count"]
            )
            if count_moved:
                # ١) الحالة اتحركت -- ده حدث جديد فعلًا مش تكرار لنفس الجملة
                mode = "active_changed"
                since = now_iso                      # الوضع اتغيّر، الساعة تبدأ من جديد
            elif elapsed is not None and elapsed >= STALE_DAYS:
                # ٢) ثبات تام طويل. السكوت هنا مش معناه إنها استقرت --
                #    معناه إن محدش لمسها. ده المكان اللي المفروض يرجع يسأل فيه.
                mode = "active_stalled"
                days = elapsed
                since = now_iso                      # اتكلم -> الساعة تصفّر، فمبيكررش كل فحص
            else:
                # لسه على نفس الحالة ومحصلش الحد -- ساكت، والساعة الأصلية شغالة.
                # ملحوظة: elapsed=None (مفيش since متسجل، أو بيانات قديمة)
                # بتقع هنا عن قصد -- **ممنوع** نخترع رقم أيام.
                mode = "passive"
                since = previous["since"] or now_iso
        else:
            mode = "passive"
            since = now_iso if current_level != previous_level else (previous["since"] or now_iso)

        decisions[dimension] = {
            "mode": mode,
            "level": current_level,
            "transitioned": current_level != previous_level,
            "days": days,
            "count": current_count,
        }
        updated_levels[dimension] = {
            "level": current_level,
            "count": current_count,
            "since": since,
        }

    _save_last_levels(updated_levels)
    return decisions
