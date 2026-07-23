# -*- coding: utf-8 -*-
"""
ADAM RUNTIME v2 -- مبسط
=====================================================
المسؤولية الوحيدة: استقبال events وتمريرها للـ Executive Brain.

ما بيفكرش.
ما بيصنفش.
ما بيختارش capability.

بيعمل حاجتين بس:
  1. يحول الـ Telegram message / scheduled job لـ BahrEvent
  2. يمرره لـ Executive Brain
  3. لو EB رجع StageError -> يحوله لـ رسالة خطا واضحة (مش صامت)

القاعدة الذهبية: EB مش بيبلع exception. Runtime مش بيبلع exception.
كل خطا بيوصل للمستخدم كرسالة حقيقية + يتسجل في اللوج.
"""

from typing import Optional
from utils.logger import logger
from executive_brain import BahrEvent, StageError


class AdamRuntime:
    """
    Runtime v2 -- Gateway فقط.

    runtime.run(telegram_msg)          -> str (response)
    runtime.run_scheduled(job, chat)   -> str | None (response)
    """

    def __init__(self, executive_brain):
        self.eb = executive_brain

    def run(self, telegram_message) -> str:
        """
        يستقبل Telegram message ويمرره لـ EB.
        لو EB رفع StageError -> رسالة خطا واضحة.
        ممنوع يبلع exception.
        """
        try:
            event = BahrEvent(
                source="user",
                chat_id=telegram_message.chat.id,
                text=getattr(telegram_message, "text", None),
            )
            return self.eb.run(event)

        except StageError as e:
            logger.error("EB StageError [" + e.stage + "]: " + str(e.original_error))
            return "حصلت مشكلة في " + e.stage + ". جرب تاني."

        except Exception as e:
            logger.error("Runtime unexpected error: " + str(e))
            return "حصلت مشكلة غير متوقعة. تم التسجيل."

    def run_scheduled(self, job_name: str, chat_id: int) -> Optional[str]:
        """
        يستقبل scheduled job ويمرره لـ EB.
        بيرجع str للـ morning brief / None للباقي.
        ممنوع يبلع exception.
        """
        try:
            event = BahrEvent(
                source="scheduler",
                chat_id=chat_id,
                job_name=job_name,
            )
            return self.eb.run(event)

        except StageError as e:
            logger.error("Scheduled StageError [" + e.stage + "]: " + str(e.original_error))
            raise  # APScheduler بيمسك ده ويسجله كـ job failure

        except Exception as e:
            logger.error("Runtime scheduled unexpected error: " + str(e))
            raise  # نفس المنطق -- مش بنبلع exceptions في الـ Runtime
