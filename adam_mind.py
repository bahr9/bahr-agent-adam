# -*- coding: utf-8 -*-
"""
ADAM MIND v2
=====================================================
المسؤولية الوحيدة: تحليل النية (Intent Analysis)

لا يعرف Firebase / Weather / Graph / اي Service.
لا ياخد قرارات تنفيذ.
بيعرف بس: يفهم الكلام ويحلله.

Fast Path  -> Keyword matching  (zero cost, zero latency)
Slow Path  -> Claude Haiku      (cheap, for ambiguous messages)

ما اتغير من v1:
  - اتشال: Thinking / Judgment / Decision
  - اتشال: CandidateUnderstanding / JudgmentResult / CognitiveCommitment
  + اتضاف: IntentAnalysis -- وحدة الناتج الوحيدة
  + اتضاف: _fast_path  -- keyword map
  + اتضاف: _deep_analyze -- Haiku fallback
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from utils.logger import logger


# ============================================================
# Confidence
# ============================================================

class Confidence(Enum):
    CERTAIN   = "certain"
    PROBABLE  = "probable"
    UNCERTAIN = "uncertain"


# ============================================================
# IntentAnalysis -- الناتج الوحيد
# ============================================================

@dataclass
class IntentAnalysis:
    """
    ده اللي بيرجعه Adam Mind للـ Executive Brain.
    EB هو اللي بيقرر بناءً عليه إيه اللي هيتعمل.
    """
    intent:                 str
    goal:                   str
    confidence:             Confidence
    missing_info:           Optional[str]
    entities:               dict
    requires_clarification: bool

    def is_clear(self) -> bool:
        return (
            self.confidence in [Confidence.CERTAIN, Confidence.PROBABLE]
            and not self.requires_clarification
        )


# ============================================================
# AdamMind
# ============================================================

class AdamMind:
    """
    خبير التحليل اللغوي -- مش صاحب قرار.

    Fast Path (keyword):   "ذكرني بالاجتماع" -> save_reminder [CERTAIN, 0ms, $0]
    Slow Path (Haiku):     "مش عارف" -> chat [PROBABLE, ~300ms, cheap]
    """

    CLEAR_INTENT_MAP = {
        "save_reminder":      ["ذكرني", "فكرني", "تذكير جديد", "remind me", "reminder"],
        "delete_reminder":    ["امسح التذكير", "احذف التذكير", "شيل التذكير"],
        "get_reminders":      ["تذكيراتي", "التذكيرات", "وريني التذكيرات", "show reminders"],
        "create_recurring":   ["تذكير متكرر", "كل يوم ذكرني", "recurring"],
        "save_memory":        ["ملاحظة جديدة", "دون", "خلي في بالك", "note this", "save note"],
        "get_memory":         ["ملاحظاتي", "ذاكرتي", "اللي حفظته", "memory notes"],
        "add_expense":        ["صرفت", "دفعت", "مصروف", "expense", "spent"],
        "get_expenses":       ["المصاريف", "صرف الشهر", "ملخص المصاريف"],
        "delete_expense":     ["امسح المصروف", "احذف المصروف"],
        "get_weather":        ["الطقس", "الجو", "weather"],
        "get_projects":       ["المشاريع", "مشاريعي", "projects", "bahr os"],
        "update_project":     ["حدث المشروع", "وضع المشروع", "update project"],
        "create_project":     ["مشروع جديد", "انشئ مشروع", "create project"],
        "get_loans":          ["الاقساط", "القسط", "ديوني", "loans"],
        "get_graph":          ["الجراف", "خريطة المعرفة", "graph"],
        "add_graph_node":     ["اضف للجراف", "سجل في الجراف", "add to graph"],
        "get_clients":        ["متابعة العملاء", "العملاء", "clients", "followup"],
        "add_client":         ["عميل جديد", "اضف عميل"],
        "eye_expert_logs":    ["عين الخبير", "اسئلة العملاء", "eye expert"],
        "backup_status":      ["الباكب", "اخر باكب", "backup"],
        "morning_brief":      ["البريف", "ملخص الصبح", "morning brief"],
    }

    COMMAND_PREFIXES = {
        "ذكرني":   "save_reminder",
        "فكرني":   "save_reminder",
        "احفظ":    "save_memory",
        "سجل":     "save_memory",
        "صرفت":    "add_expense",
        "دفعت":    "add_expense",
        "وريني":   "get_query",
        "اعرض":    "get_query",
        "امسح":    "delete_operation",
        "احذف":    "delete_operation",
        "اضف":     "add_operation",
        "انشئ":    "create_operation",
        "show":    "get_query",
        "remind":  "save_reminder",
        "delete":  "delete_operation",
        "add":     "add_operation",
    }

    def analyze(self, message: str, context: dict = None) -> IntentAnalysis:
        """
        Fast Path -> Slow Path.
        دايماً بيرجع IntentAnalysis، ما بيرفعش Exception.
        """
        if not message or not message.strip():
            return IntentAnalysis(
                intent="unknown",
                goal="رسالة فارغة",
                confidence=Confidence.UNCERTAIN,
                missing_info="الرسالة فارغة",
                entities={},
                requires_clarification=True
            )

        fast = self._fast_path(message)
        if fast:
            return fast

        return self._deep_analyze(message, context or {})

    def _fast_path(self, message: str) -> Optional[IntentAnalysis]:
        """
        Keyword matching -- zero API call.

        الترتيب الصح:
          1. CLEAR_INTENT_MAP اول -- specific keywords (اعلى دقة)
          2. COMMAND_PREFIXES تاني -- generic prefixes (fallback)

        السبب: "وريني التذكيرات" لازم يطلع get_reminders مش get_query.
        لو قلبنا الترتيب، الـ prefix "وريني" بيمسك الرسالة قبل ما
        الكلمة المحددة "التذكيرات" تتفحص.
        """
        msg_lower = message.lower().strip()

        # 1. Specific intent keywords -- الاعلى دقة اول
        for intent, keywords in self.CLEAR_INTENT_MAP.items():
            if any(kw in msg_lower for kw in keywords):
                return IntentAnalysis(
                    intent=intent,
                    goal=message,
                    confidence=Confidence.PROBABLE,
                    missing_info=None,
                    entities={"raw": message},
                    requires_clarification=False
                )

        # 2. Generic command prefixes -- fallback لو مفيش keyword محدد
        for prefix, intent in self.COMMAND_PREFIXES.items():
            if msg_lower.startswith(prefix):
                return IntentAnalysis(
                    intent=intent,
                    goal=message,
                    confidence=Confidence.CERTAIN,
                    missing_info=None,
                    entities={"raw": message},
                    requires_clarification=False
                )

        return None

    def _deep_analyze(self, message: str, context: dict) -> IntentAnalysis:
        """
        Claude Haiku للرسايل الغامضة.
        تصنيف فقط -- مش execution.
        لو فشل -> fallback آمن (intent=chat).
        """
        try:
            from services.claude_service import claude_client, CLAUDE_HAIKU_MODEL

            valid_intents = (
                "save_reminder/get_reminders/save_memory/get_memory/"
                "add_expense/get_expenses/get_weather/get_projects/"
                "update_project/get_loans/get_graph/get_clients/"
                "eye_expert_logs/backup_status/morning_brief/chat/question/unknown"
            )

            prompt = (
                "حلل نية الرسالة وارجع JSON فقط بدون اي كلام تاني.\n"
                "الـ intent الممكنة: " + valid_intents + "\n"
                '{"intent":"...","goal":"...","confidence":"certain|probable|uncertain",'
                '"missing_info":null,"entities":{},"requires_clarification":false}\n'
                "الرسالة: " + message
            )

            response = claude_client.messages.create(
                model=CLAUDE_HAIKU_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw += block.text

            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])

            data = json.loads(raw)

            return IntentAnalysis(
                intent=data.get("intent", "chat"),
                goal=data.get("goal", message),
                confidence=Confidence(data.get("confidence", "probable")),
                missing_info=data.get("missing_info"),
                entities=data.get("entities", {}),
                requires_clarification=bool(data.get("requires_clarification", False))
            )

        except Exception as e:
            # لا نبلع الخطا صامت -- نسجّل warning عشان نعرف لو التحليل فشل
            # entities بتحمل "analysis_fallback": True عشان EB يعرف ده مش تحليل حقيقي
            logger.warning("AdamMind deep_analyze fallback: " + str(e))
            return IntentAnalysis(
                intent="chat",
                goal=message,
                confidence=Confidence.PROBABLE,
                missing_info=None,
                entities={"raw": message, "analysis_fallback": True},
                requires_clarification=False
            )


adam_mind = AdamMind()
