# -*- coding: utf-8 -*-
"""
👤 ADAM Human Model — نموذج أحمد
=====================================================
مش مجرد profile — ده فهم حقيقي لأحمد.

المبدأ الدستوري:
"The Human Model is owned exclusively by the human.
 ADAM may learn from it.
 ADAM may never become the authority over it."

البنية:
- Identity     → من هو أحمد
- Family       → عيلته
- Work         → شغله وشركته
- Preferences  → أسلوبه وتفضيلاته
- Context      → سياق حياته اليومي
"""

import json
import os
from datetime import datetime
from typing import Optional

# ============================================================
# 📋 Human Model Structure
# ============================================================

DEFAULT_HUMAN_MODEL = {
    # Identity
    "name": "أحمد",
    "full_name": "أحمد جويدة",
    "nickname": "بحورة",
    "language": "arabic_egyptian",

    # Family
    "family": {
        "wife": {
            "name": "إسراء",
            "birthday": ""
        },
        "daughter": {
            "name": "غالية",
            "birthday": "16 أبريل"
        }
    },

    # Work
    "work": {
        "company": "Bahr Designs",
        "industry": "Interior Architecture & Fit-Out & Construction",
        "role": "Chief Architect & Owner",
        "tools": ["Bahr OS", "Bahr Site", "عين الخبير", "Marketing Agent"]
    },

    # Daily Routine
    "routine": {
        "morning_start": "08:00",
        "first_action": "WhatsApp",
        "focus_hours": ["08:00", "12:00"],
        "timezone": "Africa/Cairo",
        "prefers_voice": True
    },

    # Communication Style
    "communication": {
        "style": "direct",
        "detail_level": "strategic",
        "prefers_short": True,
        "language_mix": "arabic_with_english_terms"
    },

    # Known Preferences
    "preferences": {
        "morning_motivation": True,
        "proactive_alerts": True,
        "hates_repetition": True,
        "values_punctuality": True
    },

    # Meta
    "model_version": "1.0",
    "created_at": datetime.now().isoformat(),
    "last_updated": datetime.now().isoformat()
}

# ============================================================
# 🧠 Human Model Class
# ============================================================

class HumanModel:
    """
    Human Model لأحمد.

    قواعد دستورية:
    01 — أحمد يملك النموذج ده كامل
    02 — ADAM يتعلم منه — مش يعرّفه
    03 — كل inference = provisional حتى أحمد يقبلها
    04 — أحمد يقدر يصحح أي حاجة في أي وقت
    """

    MODEL_FILE = "adam_human_model.json"

    def __init__(self):
        self._model = self._load()

    def _load(self) -> dict:
        """تحميل الـ model من الملف أو إنشاء default"""
        if os.path.exists(self.MODEL_FILE):
            try:
                with open(self.MODEL_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with defaults (عشان لو في fields جديدة)
                    merged = DEFAULT_HUMAN_MODEL.copy()
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return DEFAULT_HUMAN_MODEL.copy()

    def _save(self):
        """حفظ الـ model"""
        self._model["last_updated"] = datetime.now().isoformat()
        with open(self.MODEL_FILE, "w", encoding="utf-8") as f:
            json.dump(self._model, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 📖 Read Methods
    # ============================================================

    def get(self, key: str, default=None):
        """جلب قيمة من الـ model"""
        keys = key.split(".")
        value = self._model
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def get_name(self) -> str:
        return self._model.get("nickname") or self._model.get("name", "أحمد")

    def get_family_summary(self) -> str:
        family = self._model.get("family", {})
        parts = []
        if "wife" in family:
            parts.append(f"زوجة: {family['wife']['name']}")
        if "daughter" in family:
            parts.append(f"بنت: {family['daughter']['name']}")
        return " | ".join(parts)

    def get_work_summary(self) -> str:
        work = self._model.get("work", {})
        return f"{work.get('role', '')} في {work.get('company', '')}"

    def get_context_for_adam(self) -> dict:
        """
        السياق اللي ADAM محتاجه في كل رسالة.
        مش كل الـ model — بس اللي مهم للتفاعل.
        """
        return {
            "name": self.get_name(),
            "family": self.get_family_summary(),
            "work": self.get_work_summary(),
            "style": self._model.get("communication", {}).get("style", "direct"),
            "prefers_short": self._model.get("communication", {}).get("prefers_short", True),
            "timezone": self._model.get("routine", {}).get("timezone", "Africa/Cairo"),
        }

    # ============================================================
    # ✏️ Write Methods (Human Authority Only)
    # ============================================================

    def update(self, key: str, value, provisional: bool = True) -> dict:
        """
        تحديث قيمة في الـ model.

        provisional=True → inference لحد أحمد يقبلها
        provisional=False → أحمد صرّح بيها مباشرة
        """
        keys = key.split(".")
        target = self._model
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        if provisional:
            # حفظ كـ inference مؤقتة
            if "_provisional" not in self._model:
                self._model["_provisional"] = {}
            self._model["_provisional"][key] = {
                "value": value,
                "suggested_at": datetime.now().isoformat(),
                "accepted": False
            }
            self._save()
            return {"status": "provisional", "key": key, "value": value}
        else:
            # تحديث مباشر — أحمد صرّح
            target[keys[-1]] = value
            self._save()
            return {"status": "accepted", "key": key, "value": value}

    def accept_inference(self, key: str) -> bool:
        """أحمد يقبل inference مؤقتة"""
        provisional = self._model.get("_provisional", {})
        if key in provisional:
            inference = provisional[key]
            self.update(key, inference["value"], provisional=False)
            provisional[key]["accepted"] = True
            self._save()
            return True
        return False

    def correct(self, key: str, correct_value) -> dict:
        """أحمد يصحح معلومة"""
        return self.update(key, correct_value, provisional=False)

    def get_pending_inferences(self) -> list:
        """جلب الـ inferences المؤقتة اللي لسه محتاجة موافقة"""
        provisional = self._model.get("_provisional", {})
        return [
            {"key": k, "value": v["value"], "suggested_at": v["suggested_at"]}
            for k, v in provisional.items()
            if not v.get("accepted", False)
        ]


# Instance واحد
human_model = HumanModel()
