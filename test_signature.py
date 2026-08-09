# -*- coding: utf-8 -*-
"""
اختبارات سجل التوقيع.

الاختبار الحارس الأهم هنا: **مفيش قاعدة تبقى confirmed غير لو أحمد قالها**.
لو حد (أنا أو موديل تاني) ضاف قاعدة مهنية وحطها confirmed، الاختبار ده
لازم يحمرّ -- لأن ساعتها التوقيع بقى بتاع حد تاني.
"""

import unittest

from services import signature as sig


# قايمة بيضا: اللي أحمد أكدهم بلسانه، بتاريخ.
AHMED_CONFIRMED = {
    "separate_genders": "2026-08-09",
}


class TestConfirmationIntegrity(unittest.TestCase):
    def test_only_ahmed_rules_are_confirmed(self):
        got = {r["id"] for r in sig.confirmed()}
        self.assertEqual(got, set(AHMED_CONFIRMED),
                         "قاعدة اتحطت confirmed من غير ما أحمد يقولها")

    def test_confirmed_rules_have_capture_date(self):
        for r in sig.confirmed():
            self.assertEqual(r.get("captured"), AHMED_CONFIRMED[r["id"]])

    def test_every_rule_has_valid_status(self):
        for r in sig.RULES:
            self.assertIn(r["status"], (sig.CONFIRMED, sig.PROPOSED), r["id"])


class TestRegistryShape(unittest.TestCase):
    REQUIRED = ("id", "category", "status", "text", "why", "applies_at")
    STAGES = ("brief", "layout", "materials", "lighting", "execution")

    def test_required_fields(self):
        for r in sig.RULES:
            for f in self.REQUIRED:
                self.assertTrue(r.get(f), f"{r.get('id')} ناقصه {f}")

    def test_ids_unique(self):
        ids = [r["id"] for r in sig.RULES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_stages_valid(self):
        for r in sig.RULES:
            self.assertIn(r["applies_at"], self.STAGES, r["id"])

    def test_every_rule_explains_why(self):
        # "ليه" مش زينة: القاعدة من غير سبب مبتتناقشش ومبتتلغيش
        for r in sig.RULES:
            self.assertGreater(len(r["why"]), 25, r["id"])


class TestLookups(unittest.TestCase):
    def test_get_known(self):
        self.assertIsNotNone(sig.get("separate_genders"))

    def test_get_unknown(self):
        self.assertIsNone(sig.get("مش موجودة"))

    def test_by_stage_filters(self):
        for r in sig.by_stage("lighting"):
            self.assertEqual(r["applies_at"], "lighting")

    def test_categories_are_ordered_and_unique(self):
        cats = sig.categories()
        self.assertEqual(len(cats), len(set(cats)))
        self.assertIn("الفراغ", cats)


class TestFormatting(unittest.TestCase):
    def setUp(self):
        self.text = sig.format_signature()

    def test_confirmed_section_present(self):
        self.assertIn("قواعدك", self.text)
        self.assertIn(sig.get("separate_genders")["text"], self.text)

    def test_proposed_shown_as_question_not_verdict(self):
        self.assertIn("مش جزء من توقيعك لحد ما تأكدها", self.text)

    def test_proposed_ids_shown_for_confirming(self):
        self.assertIn("[main_corridor_90]", self.text)

    def test_tells_how_to_confirm(self):
        self.assertIn("أكد", self.text)


if __name__ == "__main__":
    unittest.main()
