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
    last_levels = _get_last_levels()
    decisions = {}
    updated_levels = dict(last_levels)

    for dimension, highest in HIGHEST_TIER.items():
        dim_state = self_state.get(dimension)
        if not dim_state:
            continue
        current_level = dim_state["level"]
        previous_level = last_levels.get(dimension)

        is_active = current_level == highest and previous_level != highest
        decisions[dimension] = {
            "mode": "active" if is_active else "passive",
            "level": current_level,
            "transitioned": current_level != previous_level,
        }
        updated_levels[dimension] = current_level

    _save_last_levels(updated_levels)
    return decisions
