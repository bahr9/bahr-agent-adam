# -*- coding: utf-8 -*-
"""
EXECUTIVE BRAIN v1
=====================================================
المدير التنفيذي لـ ADAM.

المسؤوليات:
  1. استقبال الـ event من Runtime
  2. تحليل النية عبر Adam Mind
  3. جمع السياق المطلوب فقط
  4. تخطيط الخطوات
  5. تنفيذ الـ Capability المناسبة
  6. Verification
  7. Learning
  8. Response

القاعدة الذهبية:
  - كل Stage بترفع StageError لو حصل خطأ
  - ممنوع: except Exception: pass
  - ممنوع: except Exception: return None
  - Runtime (مش EB) هو اللي بيتعامل مع الـ StageError ويحوّله لرسالة خطأ للمستخدم
"""

from dataclasses import dataclass, field
from typing import Optional
from utils.logger import logger
from utils.time_utils import now_cairo


# ============================================================
# StageError -- عقد الاخطاء
# ============================================================

@dataclass
class StageError(Exception):
    """
    اي خطأ في اي Stage لازم يتحول لـ StageError.
    ممنوع يتبلع صامت.

    stage:           اسم الـ stage اللي فشل
    original_error:  الـ exception الاصلي
    recoverable:     هل ممكن يتجرب تاني؟ (للاستخدام المستقبلي)
    """
    stage:          str
    original_error: Exception
    recoverable:    bool = False

    def __str__(self):
        return "[Stage: " + self.stage + "] " + type(self.original_error).__name__ + ": " + str(self.original_error)

    def __post_init__(self):
        super().__init__(str(self))


# ============================================================
# ExecutionPlan -- ناتج مرحلة Planning
# ============================================================

@dataclass
class ExecutionPlan:
    """
    ناتج مرحلة Planning -- مش مجرد boolean.

    capability:  الـ capability المختارة
    intent:      الـ intent اللي اتصنف

    v1: capability دايماً "claude_agentic"
    v2: direct handlers للـ intents البسيطة (optimization مستقبلي)
    """
    capability: str       # "claude_agentic" | "direct_reminder" | "direct_expense" | ...
    intent:     str


# ============================================================
# BahrEvent -- وحدة الدخول
# ============================================================

@dataclass
class BahrEvent:
    """
    الـ event اللي بيجي من Runtime للـ Executive Brain.
    بسيط ومباشر -- مفيش Telegram objects جوه EB.
    """
    source:    str                    # "user" | "scheduler" | "flask"
    chat_id:   Optional[int]
    text:      Optional[str] = None
    job_name:  Optional[str] = None   # scheduler events فقط
    media_type: Optional[str] = None  # "voice" | "photo" | None


# ============================================================
# EXECUTIVE BRAIN
# ============================================================

# هذه الـ intents بتروح لـ Claude Agentic (full tool access)
CLAUDE_INTENTS = {
    "chat", "question", "unknown", "morning_brief",
    "get_query", "add_operation", "create_operation",
    "update_operation", "delete_operation",
    "save_reminder", "delete_reminder", "get_reminders", "create_recurring",
    "save_memory", "get_memory", "search_memory",
    "add_expense", "get_expenses", "delete_expense",
    "get_weather",
    "get_projects", "update_project", "create_project", "delete_project",
    "get_loans",
    "get_graph", "add_graph_node",
    "get_clients", "add_client",
    "eye_expert_logs",
    "backup_status",
}
# ملاحظة: في v1 كل حاجة بتروح لـ Claude Agentic.
# في v2 هنضيف direct handlers للـ intents البسيطة (save_reminder, add_expense, إلخ)
# عشان نوفر Claude calls للحاجات اللي مش محتاجة natural language.


class ExecutiveBrain:
    """
    EB -- المدير التنفيذي.

    Adam Mind:    خبير التحليل (بيُستدعى عند الحاجة)
    Claude:       الـ default capability للـ user requests
    Schedulers:   لهم مسار خاص (job_name -> handler مباشر)
    """

    def __init__(self, adam_mind):
        self.mind = adam_mind

    # ============================================================
    # run -- نقطة الدخول الوحيدة
    # ============================================================

    def run(self, event: BahrEvent) -> Optional[str]:
        """
        تشغيل الـ 7 Stages.
        بيرجع str (الرد) أو None (scheduled events اللي مفيش ردها).

        اي StageError بتتطلع للـ Runtime -- هو اللي يتعامل معاها.
        """
        try:
            # Scheduled Events -- مسار منفصل وسريع
            if event.source == "scheduler":
                return self._handle_scheduled(event)

            # Stage 1: Intent Analysis
            intent = self._stage_intent(event)

            # Stage 2: Context Collection -- دايماً قبل أي قرار
            context = self._stage_context(intent, event)

            # Stage 3: Planning
            plan = self._stage_plan(intent)

            # Stage 4: Execution
            result = self._stage_execute(plan, context, event)

            # Stage 5: Response Validation (مش Verification حقيقي لسه)
            self._validate_response(result, plan)

            # Stage 6: Learning
            self._stage_learn(event, result)

            # Stage 7: Response
            return self._stage_respond(result)

        except StageError:
            raise
        except Exception as e:
            raise StageError(stage="executive_brain.run", original_error=e)

    # ============================================================
    # Scheduled Events -- مسار خاص
    # ============================================================

    def _handle_scheduled(self, event: BahrEvent) -> Optional[str]:
        """
        Scheduled jobs بيعمل execute مباشر بدون intent analysis.
        EB بيعرف الـ job_name وبيروت لـ handler مناسب.
        """
        try:
            job = event.job_name or ""

            if "morning" in job:
                from morning_brief import generate_morning_brief
                return generate_morning_brief(str(event.chat_id))

            # باقي الـ scheduled jobs مش بترجع response للمستخدم مباشرة
            # (loans, backup, etc.) -- بيبعتوا رسائل من خلال الـ job function نفسها
            return None

        except Exception as e:
            raise StageError(stage="scheduled_handler[" + (event.job_name or "") + "]", original_error=e)

    # ============================================================
    # Stage 1 -- Intent Analysis
    # ============================================================

    def _stage_intent(self, event: BahrEvent):
        """Adam Mind يحلل النية."""
        try:
            return self.mind.analyze(event.text or "", {})
        except Exception as e:
            raise StageError(stage="intent_analysis", original_error=e)

    # ============================================================
    # Stage 2 -- Context Collection
    # ============================================================

    def _stage_context(self, intent, event: BahrEvent) -> dict:
        """
        اجمع السياق المطلوب بناءً على الـ intent فقط.
        مش كل حاجة في كل مرة.
        """
        try:
            context = {
                "timestamp": now_cairo().isoformat(),
                "intent": intent.intent,
            }

            # History + Memory -- دايماً للكل
            # السبب: الرسايل القصيرة زي "آه امسح" أو "لأ" محتاجة السياق
            # حتى لو الـ intent واضح -- من غير history Claude مش هيعرف إيه المقصود
            if event.chat_id:
                from services.firebase_service import get_conversation_history
                from services.memory_service import get_memory
                from services.claude_service import format_history_for_claude

                stored = get_conversation_history(event.chat_id, limit=50)
                context["history"] = format_history_for_claude(stored, limit=15)
                context["memory"] = get_memory(event.chat_id)

            return context

        except StageError:
            raise
        except Exception as e:
            raise StageError(stage="context_collection", original_error=e)

    # ============================================================
    # Stage 3 -- Planning
    # ============================================================

    def _stage_plan(self, intent) -> ExecutionPlan:
        """
        intent -> ExecutionPlan.

        v1: كل حاجة -> claude_agentic (placeholder واضح مش قرار وهمي)
        v2: direct handlers للـ intents البسيطة (future optimization)

        الفرق عن النسخة السابقة:
          - مش boolean -- object حقيقي بيوصف القرار
          - لو v2 اضافت direct_reminder -- الـ plan هيتغير هنا فقط
            من غير ما نلمس اي حاجة تانية
        """
        try:
            # TODO v2: map simple intents to direct capabilities
            # example:
            #   "save_reminder"  -> "direct_reminder"
            #   "add_expense"    -> "direct_expense"
            #   "get_weather"    -> "direct_weather"
            #
            # v1: الكل على claude_agentic
            return ExecutionPlan(
                capability="claude_agentic",
                intent=intent.intent
            )

        except Exception as e:
            raise StageError(stage="planning", original_error=e)

    # ============================================================
    # Stage 4 -- Execution
    # ============================================================

    def _stage_execute(self, plan: ExecutionPlan, context: dict, event: BahrEvent) -> str:
        """
        ينفذ الـ capability المحددة في الـ plan.
        v1: claude_agentic فقط.
        """
        try:
            if plan.capability == "claude_agentic":
                return self._call_claude_agentic(event, context)

            # Fallback آمن لو جه capability مش متعرف
            logger.warning("Unknown capability: " + plan.capability + " -- fallback to claude_agentic")
            return self._call_claude_agentic(event, context)

        except StageError:
            raise
        except Exception as e:
            raise StageError(stage="execution[" + plan.capability + "]", original_error=e)

    def _call_claude_agentic(self, event: BahrEvent, context: dict) -> str:
        """يطلب Claude Agentic مع السياق الكامل."""
        try:
            from services.claude_service import ask_claude_agentic

            result = ask_claude_agentic(
                event.text,
                event.chat_id,
                conversation_history=context.get("history", []),
                memory_summary=context.get("memory")
            )

            if not result:
                raise ValueError("Claude returned empty response")

            return result

        except StageError:
            raise
        except Exception as e:
            raise StageError(stage="claude_agentic", original_error=e)

    # ============================================================
    # Stage 5 -- Response Validation
    # (مش Verification حقيقي لسه)
    # ============================================================

    def _validate_response(self, result: str, plan: ExecutionPlan) -> None:
        """
        بيتأكد إن في response مش فاضي.

        ده response validation -- مش Verification حقيقي.
        Verification الحقيقي محتاج ExecutionResult منظم:
          - هل Firestore اتغير فعلاً؟
          - هل الـ operation اتنفذ ولا اتوهم؟
        ده شغل v2 لما يبقى فيه direct capabilities.

        حاليًا: بنتأكد إن مفيش response فاضي بعت.
        """
        try:
            if not result or not result.strip():
                raise ValueError("Empty response from capability: " + plan.capability)
        except StageError:
            raise
        except Exception as e:
            raise StageError(stage="response_validation", original_error=e)

    # ============================================================
    # Stage 6 -- Learning
    # ============================================================

    # كلمات الموافقة القصيرة الصرفة -- مش قرارات
    _ACK_WORDS = {
        "ok", "okay", "تمام", "ماشي", "اوك", "اوكي", "آه", "اه", "ايوه",
        "يلا", "فاهم", "عظيم", "برافو", "شكرا", "شكراً", "thanks",
        "thank", "good", "great", "nice", "هيه", "يا سلام", "تمام."
    }

    # كلمات تدل على قرار أو تصحيح أو اعتماد -- حتى لو الرسالة قصيرة
    _DECISION_SIGNALS = {
        "اعتمد", "اعتمده", "اعتمدي", "موافق", "مرفوض", "مستقل", "مرتبط",
        "صح", "غلط", "لأ", "لا", "نفذ", "شيل", "امسح", "حدّث", "عدّل",
        "draft", "رسمي", "قرار", "اختار", "الخيار", "الثاني", "الأول",
        "الاسم", "المشروع", "تصحيح", "هو ده", "ده الصح", "مش ده",
        "confirm", "reject", "approved", "cancel"
    }

    def _fast_filter(self, event: BahrEvent, result: str) -> Optional[bool]:
        """
        الطبقة الأولى -- فلتر سريع بدون API.

        بيرجع:
        - False: مؤكد مش يستاهل (وقف هنا)
        - None:  مش واضح أو ممكن قرار (روح للطبقة التانية)

        قاعدة أساسية: لو الرسالة قصيرة بس ممكن تكون اعتماد/رفض/تصحيح/قرار
        → روح للطبقة التانية، ما تستبعدهاش.
        """
        msg = (event.text or "").strip()
        reply = (result or "").strip()

        # فاضي أو خطأ -- مؤكد لأ
        if not msg or not reply:
            return False
        if reply.startswith("❌"):
            return False

        words = msg.split()
        msg_lower = msg.lower()

        # لو فيه إشارة قرار -- روح للطبقة التانية حتى لو الرسالة قصيرة
        for signal in self._DECISION_SIGNALS:
            if signal in msg_lower:
                return None

        # كلمة موافقة صرفة (مش فيها أي محتوى تاني) -- مؤكد لأ
        if len(words) == 1 and msg_lower in self._ACK_WORDS:
            return False

        # رسالتين كلمات كلهم موافقة -- مؤكد لأ
        if len(words) <= 2 and all(w in self._ACK_WORDS for w in words):
            return False

        # رسالة قصيرة جداً والرد قصير -- مش واضح، روح للطبقة التانية
        if len(words) <= 4 and len(reply) < 50:
            return None

        # باقي -- مش واضح، روح للطبقة التانية
        return None

    def _decide_learning(self, event: BahrEvent, result: str) -> bool:
        """
        LearningDecision -- طبقتين:

        الطبقة 1 (بدون API): فلتر سريع للحالات الواضحة
        الطبقة 2 (Haiku):   قرار ذكي للحالات الغامضة

        بيرجع True لو يستاهل يتحفظ، False لو لأ.
        """
        # الطبقة الأولى
        fast_result = self._fast_filter(event, result)
        if fast_result is not None:
            return fast_result

        # الطبقة الثانية -- Haiku بيقرر
        try:
            from services.claude_service import should_store_in_memory
            return should_store_in_memory(event.text, result)
        except Exception as e:
            logger.warning("LearningDecision layer2 error: " + str(e))
            return True  # افتراضي آمن -- أحسن تتحفظ من تتفوت

    def _stage_learn(self, event: BahrEvent, result: str) -> None:
        """
        حفظ المحادثة وتحديث الذاكرة الدائمة بقرار ذكي.

        save_conversation: دايماً (تاريخ المحادثة الكامل)
        update_memory: بس لو LearningDecision قال آه

        Learning مش بتوقف الـ pipeline لو فشل.
        """
        try:
            if not event.text or not event.chat_id:
                return

            from services.firebase_service import save_conversation
            from services.memory_service import update_memory

            # تاريخ المحادثة -- دايماً
            save_conversation(event.chat_id, event.text, result)

            # الذاكرة الدائمة -- بقرار ذكي
            should_store = self._decide_learning(event, result)
            if should_store:
                update_memory(event.chat_id, event.text, result)
                logger.info("Learning: memory updated for chat " + str(event.chat_id))
            else:
                logger.info("Learning: skipped by LearningDecision")

        except Exception as e:
            logger.warning("Learning stage warning: " + str(e))

    # ============================================================
    # Stage 7 -- Response
    # ============================================================

    def _stage_respond(self, result: str) -> str:
        """رجّع الـ result كما هو."""
        try:
            return result or "تمام يا أحمد."
        except Exception as e:
            raise StageError(stage="response", original_error=e)
