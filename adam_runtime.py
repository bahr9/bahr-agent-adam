# -*- coding: utf-8 -*-
"""
⚙️ ADAM Runtime — v1
=====================================================
تنفيذ ADAM_RUNTIME_BLUEPRINT.md

9 مراحل:
    1. Event Reception
    2. Event Classification
    3. Context Collection
    4. Decision Making
    5. Capability Selection
    6. Execution
    7. Verification
    8. Learning
    9. Response Delivery
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
from datetime import datetime


# ============================================================
# 📦 Event Types
# ============================================================

class EventType(Enum):
    TEXT      = "text"
    VOICE     = "voice"
    IMAGE     = "image"
    DOCUMENT  = "document"
    SCHEDULED = "scheduled"
    COMMAND   = "command"
    UNKNOWN   = "unknown"


class EventSource(Enum):
    AHMED     = "ahmed"
    SCHEDULER = "scheduler"
    SYSTEM    = "system"


# ============================================================
# 📋 Runtime Execution — وحدة التنفيذ
# ============================================================

@dataclass
class RuntimeEvent:
    """الحدث الداخل للـ Runtime"""
    event_type: EventType
    source: EventSource
    text: Optional[str] = None
    chat_id: Optional[int] = None
    raw_data: Optional[Any] = None
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RuntimeExecution:
    """
    وحدة التنفيذ الكاملة.
    بتتشيل في كل مراحل الـ Runtime.
    """
    # Stage 1 — Reception
    event: RuntimeEvent

    # Stage 2 — Classification
    event_category: Optional[str] = None  # user_request, scheduled, system

    # Stage 3 — Context
    context: dict = field(default_factory=dict)

    # Stage 4 — Decision
    execution_goal: Optional[str] = None
    requires_clarification: bool = False
    clarification_reason: Optional[str] = None

    # Stage 5 — Capability Selection
    selected_capability: Optional[str] = None  # claude, firebase, deterministic

    # Stage 6 — Execution
    execution_result: Optional[Any] = None
    execution_success: bool = False
    execution_error: Optional[str] = None

    # Stage 7 — Verification
    verified: bool = False
    verification_notes: Optional[str] = None

    # Stage 8 — Learning
    learning_record: Optional[dict] = None

    # Stage 9 — Response
    final_response: Optional[str] = None


# ============================================================
# ⚙️ ADAM Runtime Engine
# ============================================================

class AdamRuntime:
    """
    ADAM Runtime Engine.

    كل رسالة بتعدي على 9 مراحل.
    كل مرحلة بتضيف للـ RuntimeExecution.
    """

    def __init__(self, human_model, adam_mind):
        self.human_model = human_model
        self.mind = adam_mind
        self._capabilities = {}

    def register_capability(self, name: str, handler):
        """تسجيل capability"""
        self._capabilities[name] = handler

    # ============================================================
    # Stage 1 — Event Reception
    # ============================================================

    def receive(self, telegram_message) -> RuntimeExecution:
        """
        Stage 1: استقبال الحدث وتحويله لـ RuntimeEvent.
        لا يفسر — بس يستقبل.
        """
        text = getattr(telegram_message, 'text', None)
        chat_id = telegram_message.chat.id

        if text and text.startswith('/'):
            event_type = EventType.COMMAND
        elif text:
            event_type = EventType.TEXT
        elif getattr(telegram_message, 'voice', None):
            event_type = EventType.VOICE
        elif getattr(telegram_message, 'photo', None):
            event_type = EventType.IMAGE
        elif getattr(telegram_message, 'document', None):
            event_type = EventType.DOCUMENT
        else:
            event_type = EventType.UNKNOWN

        event = RuntimeEvent(
            event_type=event_type,
            source=EventSource.AHMED,
            text=text,
            chat_id=chat_id,
            raw_data=telegram_message
        )

        return RuntimeExecution(event=event)

    def receive_scheduled(self, job_name: str, chat_id: int) -> RuntimeExecution:
        """Stage 1: استقبال حدث مجدول"""
        event = RuntimeEvent(
            event_type=EventType.SCHEDULED,
            source=EventSource.SCHEDULER,
            chat_id=chat_id,
            metadata={"job_name": job_name}
        )
        return RuntimeExecution(event=event)

    # ============================================================
    # Stage 2 — Event Classification
    # ============================================================

    def classify(self, execution: RuntimeExecution) -> RuntimeExecution:
        """
        Stage 2: تصنيف الحدث.
        لا يفكر — بس يصنف.
        """
        event = execution.event

        if event.source == EventSource.SCHEDULER:
            execution.event_category = "scheduled_event"
        elif event.event_type == EventType.COMMAND:
            execution.event_category = "command"
        elif event.event_type == EventType.TEXT:
            execution.event_category = "user_request"
        elif event.event_type in [EventType.VOICE, EventType.IMAGE]:
            execution.event_category = "media_request"
        else:
            execution.event_category = "unknown"

        return execution

    # ============================================================
    # Stage 3 — Context Collection
    # ============================================================

    def collect_context(self, execution: RuntimeExecution) -> RuntimeExecution:
        """
        Stage 3: جمع السياق المطلوب فقط.
        لا يفكر — بس يجمع.
        """
        # Human Model context دايماً
        execution.context["human"] = self.human_model.get_context_for_adam()

        # لو في text — نضيف معلومات السياق
        if execution.event.text:
            execution.context["message"] = execution.event.text
            execution.context["message_length"] = len(execution.event.text.split())

        # لو scheduled — نضيف job info
        if execution.event.source == EventSource.SCHEDULER:
            execution.context["job"] = execution.event.metadata.get("job_name", "")

        return execution

    # ============================================================
    # Stage 4 — Decision Making
    # ============================================================

    def decide(self, execution: RuntimeExecution) -> RuntimeExecution:
        """
        Stage 4: تحديد الـ Execution Goal.
        هنا بيدخل ADAM Mind.
        """
        event = execution.event

        # Scheduled events → goal واضح
        if execution.event_category == "scheduled_event":
            job = execution.context.get("job", "")
            if "morning" in job:
                execution.execution_goal = "deliver_morning_brief"
            elif "reminder" in job:
                execution.execution_goal = "deliver_reminder"
            else:
                execution.execution_goal = "deliver_scheduled"
            return execution

        # User requests → ADAM Mind يفكر
        if execution.event_category == "user_request" and event.text:
            commitment = self.mind.process(
                event.text,
                {"human_context": execution.context.get("human", {})}
            )

            if commitment.should_ask_clarification():
                execution.requires_clarification = True
                execution.clarification_reason = commitment.human_input_reason
                execution.execution_goal = "request_clarification"
            else:
                execution.execution_goal = "process_user_request"

        return execution

    # ============================================================
    # Stage 5 — Capability Selection
    # ============================================================

    def select_capability(self, execution: RuntimeExecution) -> RuntimeExecution:
        """
        Stage 5: اختيار الـ capability المناسبة.
        Deterministic قبل AI.
        """
        goal = execution.execution_goal

        if goal == "request_clarification":
            execution.selected_capability = "deterministic"

        elif goal == "deliver_morning_brief":
            execution.selected_capability = "morning_brief"

        elif goal == "deliver_reminder":
            execution.selected_capability = "reminder"

        elif goal == "process_user_request":
            # Claude هو الـ default للـ user requests
            execution.selected_capability = "claude"

        else:
            execution.selected_capability = "claude"

        return execution

    # ============================================================
    # Stage 6 — Execution
    # ============================================================

    def execute(self, execution: RuntimeExecution) -> RuntimeExecution:
        """Stage 6: تنفيذ الـ capability المختارة."""
        capability = execution.selected_capability

        if capability == "deterministic":
            # رد مباشر بدون AI
            execution.execution_result = (
                f"🤔 {execution.clarification_reason}\n\nتقدر توضحلي أكتر؟"
            )
            execution.execution_success = True

        elif capability in self._capabilities:
            try:
                handler = self._capabilities[capability]
                result = handler(execution)
                execution.execution_result = result
                execution.execution_success = True
            except Exception as e:
                execution.execution_error = str(e)
                execution.execution_success = False

        else:
            execution.execution_error = f"Capability not found: {capability}"
            execution.execution_success = False

        return execution

    # ============================================================
    # Stage 7 — Verification
    # ============================================================

    def verify(self, execution: RuntimeExecution) -> RuntimeExecution:
        """Stage 7: التأكد إن النتيجة مناسبة للـ goal."""
        if not execution.execution_success:
            execution.verified = False
            execution.verification_notes = f"Execution failed: {execution.execution_error}"
        elif execution.execution_result:
            execution.verified = True
            execution.verification_notes = "Result produced successfully"
        else:
            execution.verified = False
            execution.verification_notes = "No result produced"

        return execution

    # ============================================================
    # Stage 8 — Learning
    # ============================================================

    def learn(self, execution: RuntimeExecution) -> RuntimeExecution:
        """Stage 8: تسجيل المعرفة من التنفيذ."""
        if execution.verified and execution.event.text:
            execution.learning_record = {
                "message": execution.event.text,
                "goal": execution.execution_goal,
                "capability": execution.selected_capability,
                "success": execution.execution_success,
                "timestamp": datetime.now().isoformat()
            }
        return execution

    # ============================================================
    # Stage 9 — Response Delivery
    # ============================================================

    def deliver(self, execution: RuntimeExecution) -> RuntimeExecution:
        """Stage 9: تسليم الرد النهائي."""
        if execution.execution_result:
            execution.final_response = execution.execution_result
        elif not execution.execution_success:
            execution.final_response = "❌ حصلت مشكلة. جرب تاني."
        else:
            execution.final_response = "تمام يا أحمد."

        return execution

    # ============================================================
    # 🔄 Full Lifecycle
    # ============================================================

    def run(self, telegram_message) -> RuntimeExecution:
        """
        تشغيل الـ 9 مراحل كاملة على رسالة Telegram.
        """
        execution = self.receive(telegram_message)
        execution = self.classify(execution)
        execution = self.collect_context(execution)
        execution = self.decide(execution)
        execution = self.select_capability(execution)
        execution = self.execute(execution)
        execution = self.verify(execution)
        execution = self.learn(execution)
        execution = self.deliver(execution)
        return execution

    def run_scheduled(self, job_name: str, chat_id: int) -> RuntimeExecution:
        """تشغيل الـ 9 مراحل على حدث مجدول."""
        execution = self.receive_scheduled(job_name, chat_id)
        execution = self.classify(execution)
        execution = self.collect_context(execution)
        execution = self.decide(execution)
        execution = self.select_capability(execution)
        execution = self.execute(execution)
        execution = self.verify(execution)
        execution = self.learn(execution)
        execution = self.deliver(execution)
        return execution
