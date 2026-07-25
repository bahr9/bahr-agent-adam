# -*- coding: utf-8 -*-
"""
🖇️ Renderer -- ADAM Self-State & Observation System (Architecture v2)
=====================================================
الآلية الحتمية اللي بتقفل مشكلة "الموديل بيكتب رقم/نص استنتاج خام"
بالكامل. Companionship (LLM) بتكتب نص فيه *مراجع بالاسم* بس (Slots)،
زي `{unresolved_conflict.count}` أو `{inference:unresolved_conflict_high}`
-- والملف ده هو الوحيد اللي بيملأها بقيم حقيقية من الـ Meaning Packet.

**صفر LLM هنا.** استبدال نصي (regex substitution) بحت -- نفس المدخلات
بتدّي نفس المخرجات بالظبط كل مرة.

قاعدة صارمة: أي slot بيشاور لحقل أو استنتاج مش موجود فعليًا في الـ
Meaning Packet المُعطى بيرفع UnknownSlotError فورًا -- **مفيش "تمرير
بصمت"**. ده بيمنع أي محاولة (متعمّدة أو غلطة) من الموديل يشاور على حاجة
مش موجودة أصلًا.
"""

import re

SLOT_PATTERN = re.compile(r"\{([\w\.\:]+)\}")


class UnknownSlotError(ValueError):
    """بترفع لو template فيه slot بيشاور لحاجة مش موجودة في الـ Meaning Packet."""
    pass


def extract_slots(template: str) -> list:
    """يرجع كل أسماء الـ slots الموجودة في نص معيّن (من غير ملء)."""
    return SLOT_PATTERN.findall(template)


def render(template: str, meaning_packet: dict) -> str:
    """
    يملأ كل الـ slots في template بقيم حقيقية من meaning_packet.
    - `{field.name}` -> قيمة referenced_facts[field.name]
    - `{inference:rule_id}` -> نص fired_inferences اللي rule_id بتاعه يطابق

    بيرفع UnknownSlotError فورًا لو أي slot بيشاور لحاجة مش موجودة.
    """
    referenced_facts = meaning_packet.get("referenced_facts", {})
    fired_inference_texts = {
        inf["rule_id"]: inf["text"] for inf in meaning_packet.get("fired_inferences", [])
    }

    def replace(match: re.Match) -> str:
        slot = match.group(1)
        if slot.startswith("inference:"):
            rule_id = slot[len("inference:"):]
            if rule_id not in fired_inference_texts:
                raise UnknownSlotError(
                    f"inference slot '{{{slot}}}' مش من ضمن fired_inferences المتاحة "
                    f"({list(fired_inference_texts.keys())})"
                )
            return fired_inference_texts[rule_id]

        if slot not in referenced_facts:
            raise UnknownSlotError(
                f"fact slot '{{{slot}}}' مش من ضمن referenced_facts المتاحة "
                f"({list(referenced_facts.keys())})"
            )
        return str(referenced_facts[slot])

    return SLOT_PATTERN.sub(replace, template)
