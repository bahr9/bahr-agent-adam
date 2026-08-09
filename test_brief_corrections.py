# -*- coding: utf-8 -*-
"""
اختبارات تصحيحات أحمد على البريف.

المبدأ اللي بتحرسه: **التصحيح طبقة، مش تعديل.**
  - `answers` كلام العميل، ثابت للأبد (دليل — CONSTITUTION.md §0).
  - `corrections` تصحيح أحمد فوقه.
  - القواعد بتشتغل على المصحَّح، والعرض بيوري الاتنين.

لو حد خلّى التصحيح يكتب فوق `answers`، الاختبارات دي بتحمرّ.
"""

import unittest

from services import brief_reader as br


def brief(answers, corrections=None, final=True, name="عميل"):
    return {
        "client_name": name,
        "is_final": final,
        "answers": answers,
        "corrections": corrections or {},
    }


def ids(read):
    return {f["id"] for f in read["flags"]}


class TestEffectiveAnswers(unittest.TestCase):
    def test_no_corrections_passes_through(self):
        row = brief({"نوع الوحدة": "شقة"})
        self.assertEqual(br.effective_answers(row)["نوع الوحدة"], "شقة")

    def test_correction_wins(self):
        row = brief({"نوع الوحدة": "شقة"},
                    {"نوع الوحدة": {"to": "دوبلكس", "at": "2026-08-10"}})
        self.assertEqual(br.effective_answers(row)["نوع الوحدة"], "دوبلكس")

    def test_original_never_mutated(self):
        row = brief({"نوع الوحدة": "شقة"},
                    {"نوع الوحدة": {"to": "دوبلكس", "at": "2026-08-10"}})
        br.effective_answers(row)
        br.read_brief(row)
        br.format_read(row)
        self.assertEqual(row["answers"]["نوع الوحدة"], "شقة",
                         "التصحيح كتب فوق كلام العميل — الدليل اتبوّظ")

    def test_correction_can_add_missing_answer(self):
        row = brief({}, {"نوع الوحدة": {"to": "فيلا", "at": "2026-08-10"}})
        self.assertEqual(br.effective_answers(row)["نوع الوحدة"], "فيلا")

    def test_malformed_correction_ignored(self):
        row = brief({"نوع الوحدة": "شقة"}, {"نوع الوحدة": "دوبلكس"})  # مش dict
        self.assertEqual(br.effective_answers(row)["نوع الوحدة"], "شقة")

    def test_missing_corrections_key_safe(self):
        self.assertEqual(br.effective_answers({"answers": {"أ": 1}})["أ"], 1)


class TestRulesUseCorrectedValues(unittest.TestCase):
    """القاعدة لازم تشوف الصح مش الغلط — ده كل الغرض من التصحيح."""

    BASE = {
        "شمول الميزانية": "كل حاجة", "الميزانية": "1.25M", "الخدمة": "تصميم وتنفيذ",
    }

    def test_rule_silent_on_client_answer(self):
        # شقة: قاعدة الميزانية مبتولعش
        read = br.read_brief(brief(dict(self.BASE, **{"نوع الوحدة": "شقة"})))
        self.assertNotIn("budget_scope", ids(read))

    def test_rule_fires_after_correction(self):
        # أحمد صحّحها لدوبلكس بعد المعاينة -> القاعدة لازم تولع
        read = br.read_brief(brief(
            dict(self.BASE, **{"نوع الوحدة": "شقة"}),
            {"نوع الوحدة": {"to": "دوبلكس", "at": "2026-08-10", "why": "اتأكدت في المعاينة"}}))
        self.assertIn("budget_scope", ids(read))

    def test_correction_can_silence_a_rule(self):
        answers = {"ريحة الأكل": "لازم تتحبس في المطبخ", "المطبخ مفتوح": "مفتوح على الريسبشن"}
        self.assertIn("kitchen_contradiction", ids(br.read_brief(brief(answers))))
        read = br.read_brief(brief(answers, {"المطبخ مفتوح": {"to": "مقفول", "at": "x"}}))
        self.assertNotIn("kitchen_contradiction", ids(read))


class TestDisplayShowsBoth(unittest.TestCase):
    def test_fact_line_shows_client_original(self):
        text = br.format_read(brief(
            {"نوع الوحدة": "شقة"},
            {"نوع الوحدة": {"to": "دوبلكس", "at": "2026-08-10"}}))
        self.assertIn("دوبلكس", text)
        self.assertIn("العميل قال: شقة", text)

    def test_added_answer_marked_as_ahmeds(self):
        text = br.format_read(brief({}, {"نوع الوحدة": {"to": "فيلا", "at": "x"}}))
        self.assertIn("أحمد ضافها", text)

    def test_non_fact_correction_listed_separately(self):
        text = br.format_read(brief(
            {"مقاس السرير": "١٦٠ سم"},
            {"مقاس السرير": {"to": "١٨٠ سم", "at": "x", "why": "اتفقنا في المعاينة"}}))
        self.assertIn("تصحيحاتك", text)
        self.assertIn("١٨٠ سم", text)
        self.assertIn("العميل قال: ١٦٠ سم", text)
        self.assertIn("اتفقنا في المعاينة", text)

    def test_clean_brief_has_no_correction_noise(self):
        text = br.format_read(brief({"نوع الوحدة": "شقة"}))
        self.assertNotIn("تصحيحاتك", text)
        self.assertNotIn("✎", text)


class TestReadExposesCorrections(unittest.TestCase):
    def test_read_carries_corrections(self):
        fixes = {"نوع الوحدة": {"to": "دوبلكس", "at": "x"}}
        self.assertEqual(br.read_brief(brief({"نوع الوحدة": "شقة"}, fixes))["corrections"], fixes)

    def test_empty_when_none(self):
        self.assertEqual(br.read_brief(brief({"أ": 1}))["corrections"], {})


if __name__ == "__main__":
    unittest.main()
