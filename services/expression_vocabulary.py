# -*- coding: utf-8 -*-
"""
📖 Closed Vocabulary -- ADAM Self-State & Observation System (Stage 6 + 7)
=====================================================
قاموس مقفول: كل (dimension, level, mode) له نص واحد بس، مكتوب مسبقًا هنا.
مفيش صياغة حرة لا هنا ولا في أي حاجة بتستخدم الملف ده. الملف ده **كود**،
مش prompt -- تعديل أي نص لازم يمر بمراجعة أحمد زي أي تعديل كود تاني.

القرار المقفول (اعتماد أحمد 2026-07-24): الموديل بيختار من الجمل دي، مش
بيؤلف جملة جديدة. الـ Active entries مش بتتحط قدام الموديل خالص -- بتتقرا
من هنا مباشرة من services/verified_expression.py (send_active_expression)
من غير أي مرور على LLM.
"""

CLOSED_VOCABULARY = {
    # --- unresolved_conflict ---
    ("unresolved_conflict", "none", "passive"): "مفيش أي تعارض معلّق دلوقتي.",
    ("unresolved_conflict", "elevated", "passive"): "عندي {count} تعارض غير محلول محتاج مراجعتك.",
    ("unresolved_conflict", "high", "passive"): "عندي {count} تعارضات غير محلولة، وده رفع حالة المراجعة.",
    ("unresolved_conflict", "high", "active"): "تنبيه: ظهر تعارض غير محلول يحتاج مراجعتك.",

    # --- pending_obligation_load ---
    ("pending_obligation_load", "none", "passive"): "مفيش أي قسط متأخر عن ميعاده دلوقتي.",
    ("pending_obligation_load", "light", "passive"): "فيه {count} قسط متأخر عن ميعاده، محتاج مراجعة.",
    ("pending_obligation_load", "concern", "passive"): "فيه {count} أقساط متأخرة عن ميعادها، محتاجة متابعة قريبة.",
    ("pending_obligation_load", "concern", "active"): "تنبيه: {count} أقساط متأخرة عن ميعادها.",

    # --- tracking_stability ---
    # مفيش entry بـ mode="active" هنا خالص -- قرار Stage 5.1 مقفول: البُعد
    # ده مستبعد من decision_engine.HIGHEST_TIER عمدًا، فمستحيل يوصل هنا.
    ("tracking_stability", "none", "passive"): "معدل التصحيحات في آخر 30 يوم عادي.",
    ("tracking_stability", "frequent_corrections", "passive"): "فيه {count} تصحيحات صريحة في آخر 30 يوم -- ملاحظة موضوعية، مش مؤشر مشكلة.",
}

# لما الدليل ناقص أو البُعد مش معروف -- قاموس مقفول منفصل، مفيش تخمين هنا برضه.
VERIFIED_FALSE_VOCABULARY = {
    "unresolved_conflict": "مش قادر أتأكد من حالة التعارضات دلوقتي -- المعلومة ناقصة.",
    "pending_obligation_load": "مش قادر أتأكد من حالة الالتزامات المتأخرة دلوقتي -- المعلومة ناقصة.",
    "tracking_stability": "مش قادر أتأكد من معدل التصحيحات دلوقتي -- المعلومة ناقصة.",
}

_GENERIC_VERIFIED_FALSE = "مش قادر أتأكد من الحالة دي دلوقتي -- المعلومة ناقصة."


def get_template(dimension: str, level: str, mode: str):
    """يرجع النص المسجّل، أو None لو مفيش entry مسجّل لـ (dimension, level, mode) دي."""
    return CLOSED_VOCABULARY.get((dimension, level, mode))


def render_verified_false(dimension: str) -> str:
    """النص المقفول لحالة verified=false -- وصف نقص المعلومة بس، مفيش تخمين."""
    return VERIFIED_FALSE_VOCABULARY.get(dimension, _GENERIC_VERIFIED_FALSE)
