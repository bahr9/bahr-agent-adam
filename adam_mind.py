# -*- coding: utf-8 -*-
"""
🧠 THE ADAM MIND — v1
=====================================================
ترجمة THE_ADAM_MIND.md لكود Python.

ثلاث عمليات معرفية فقط:
    Thinking  → يولد فهوم محتملة
    Judgment  → يختار الأكثر منطقية
    Decision  → يحدد الالتزام المعرفي

Execution خارج النطاق.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ============================================================
# 📊 Epistemic States — حالات اليقين
# من ADAM_HUMILITY.md
# ============================================================

class Confidence(Enum):
    CERTAIN   = "certain"    # متأكد — معلومة موثقة
    PROBABLE  = "probable"   # محتمل — استنتاج منطقي
    UNCERTAIN = "uncertain"  # مش متأكد — محتاج توضيح


# ============================================================
# 💭 Thinking Output
# ============================================================

@dataclass
class CandidateUnderstanding:
    """فهم محتمل للموقف"""
    description: str
    confidence: Confidence
    reasoning: str
    requires_clarification: bool = False


# ============================================================
# ⚖️ Judgment Output
# ============================================================

@dataclass
class JudgmentResult:
    """ناتج تقييم الفهوم المحتملة"""
    selected: CandidateUnderstanding
    confidence: Confidence
    acknowledged_uncertainty: str
    alternatives_count: int = 0

    def is_reliable(self) -> bool:
        return self.confidence in [Confidence.CERTAIN, Confidence.PROBABLE]


# ============================================================
# 🎯 Decision Output
# ============================================================

@dataclass
class CognitiveCommitment:
    """الالتزام المعرفي — ناتج عملية Decision"""
    commitment: str
    confidence: Confidence
    requires_human_input: bool = False
    human_input_reason: Optional[str] = None
    action_direction: Optional[str] = None

    def should_ask_clarification(self) -> bool:
        return self.requires_human_input and self.confidence == Confidence.UNCERTAIN


# ============================================================
# 🧠 THE ADAM MIND
# ============================================================

class AdamMind:
    """
    THE ADAM MIND — العقل المعرفي لـ ADAM.

    يعمل مع Human Model لفهم أحمد بشكل أعمق.
    """

    # كلمات دالة على نية واضحة
    CLEAR_INTENT_KEYWORDS = [
        # أوامر
        "ذكرني", "فكرني", "سجل", "احفظ", "امسح", "عدل", "اضف", "وريني", "اعرض",
        # استفسارات
        "ايه", "كام", "امتى", "فين", "مين", "ليه", "ازاى",
        # موضوعات
        "مشروع", "تذكير", "جراف", "مصاريف", "فاتورة", "قسط",
        "فريق", "عميل", "موقع", "تقرير",
        # English
        "project", "remind", "save", "show", "delete", "graph",
        # قائمة ADAM
        "الطقس", "المصاريف", "المشاريع", "التذكيرات", "الذاكرة", "الخبير",
        "الاقساط", "الجراف", "ملخص", "حالة", "متأخر", "جاية",
        "اوك", "ماشي", "تمام", "آه", "اه", "يلا", "ok", "fahem", "فاهم"
    ]

    def thinking(self, situation: str, context: dict = None) -> list:
        """
        Generate candidate understandings.
        Starts: situation requires understanding.
        Ends: one or more candidates exist.
        """
        context = context or {}
        candidates = []

        # الفهم الأساسي
        candidates.append(CandidateUnderstanding(
            description=situation,
            confidence=Confidence.PROBABLE,
            reasoning="الفهم الظاهر للموقف"
        ))

        # لو في Human Model context
        if context.get("human_context"):
            candidates.append(CandidateUnderstanding(
                description=f"في سياق شغل أحمد: {situation}",
                confidence=Confidence.PROBABLE,
                reasoning=f"بناءً على Human Model: {context['human_context']}"
            ))

        # لو الرسالة قصيرة جداً
        word_count = len(situation.strip().split())
        has_clear_intent = any(
            kw in situation.lower()
            for kw in self.CLEAR_INTENT_KEYWORDS
        )

        if word_count < 3 and not has_clear_intent:
            candidates.append(CandidateUnderstanding(
                description=f"رسالة غير واضحة: {situation}",
                confidence=Confidence.UNCERTAIN,
                reasoning="الرسالة قصيرة جداً",
                requires_clarification=True
            ))

        return candidates

    def judgment(self, candidates: list) -> JudgmentResult:
        """
        Determine most justified understanding.
        Starts: candidates available.
        Ends: most justified identified.
        """
        if not candidates:
            return JudgmentResult(
                selected=CandidateUnderstanding(
                    description="لا يوجد فهم",
                    confidence=Confidence.UNCERTAIN,
                    reasoning="مفيش candidates"
                ),
                confidence=Confidence.UNCERTAIN,
                acknowledged_uncertainty="مفيش معلومات كافية"
            )

        # ترتيب حسب اليقين
        priority = {
            Confidence.CERTAIN: 0,
            Confidence.PROBABLE: 1,
            Confidence.UNCERTAIN: 2
        }

        sorted_candidates = sorted(
            candidates,
            key=lambda c: (priority[c.confidence], c.requires_clarification)
        )

        best = sorted_candidates[0]
        uncertain_count = sum(
            1 for c in candidates
            if c.confidence == Confidence.UNCERTAIN
        )

        uncertainty = (
            f"فيه {uncertain_count} فهم غير مؤكد"
            if uncertain_count > 0
            else "الفهم المختار هو الأوضح"
        )

        return JudgmentResult(
            selected=best,
            confidence=best.confidence,
            acknowledged_uncertainty=uncertainty,
            alternatives_count=len(candidates) - 1
        )

    def decision(
        self,
        judgment: JudgmentResult,
        original_situation: str = ""
    ) -> CognitiveCommitment:
        """
        Establish cognitive commitment.
        Starts: reliable judgment available.
        Ends: cognitive commitment established.
        """

        # Humility Rule 1: لو غير موثوق → اسأل
        if not judgment.is_reliable():
            return CognitiveCommitment(
                commitment=f"ADAM غير متأكد: {judgment.selected.description}",
                confidence=Confidence.UNCERTAIN,
                requires_human_input=True,
                human_input_reason=judgment.acknowledged_uncertainty,
                action_direction="اسأل للتوضيح"
            )

        # Humility Rule 2: رسالة قصيرة + مش واضحة → اسأل
        word_count = len(original_situation.strip().split())
        has_clear_intent = any(
            kw in original_situation.lower()
            for kw in self.CLEAR_INTENT_KEYWORDS
        )

        if word_count < 3 and not has_clear_intent:
            return CognitiveCommitment(
                commitment=f"رسالة غير واضحة: {original_situation}",
                confidence=Confidence.UNCERTAIN,
                requires_human_input=True,
                human_input_reason="الرسالة قصيرة جداً — مش واضح المقصود",
                action_direction="اسأل للتوضيح"
            )

        # القرار الموثوق
        return CognitiveCommitment(
            commitment=judgment.selected.description,
            confidence=judgment.confidence,
            requires_human_input=judgment.selected.requires_clarification,
            human_input_reason=(
                "يحتاج توضيح من أحمد"
                if judgment.selected.requires_clarification else None
            ),
            action_direction="تصرف بناءً على الفهم المحدد"
        )

    def process(
        self,
        situation: str,
        context: dict = None
    ) -> CognitiveCommitment:
        """
        الدورة المعرفية الكاملة:
        Thinking → Judgment → Decision
        """
        candidates = self.thinking(situation, context)
        judgment_result = self.judgment(candidates)
        commitment = self.decision(judgment_result, situation)
        return commitment


# Instance واحد
adam_mind = AdamMind()
