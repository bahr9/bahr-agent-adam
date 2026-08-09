# -*- coding: utf-8 -*-
"""
اختبارات سجل التوقيع.

الحارس الأهم: **مفيش قاعدة تدّعي إن أحمد قالها إلا لو قالها فعلًا.**
كل القواعد شغالة، بس اللي `origin=AHMED` نابعة منه، والباقي معرفة مهنية
اعتمدها. لو حد (أنا أو موديل تاني) حط قاعدة جديدة بـ origin=ahmed،
الاختبار ده بيحمرّ -- لأن ساعتها التوقيع بيدّعي أصل مش بتاعه.
"""

import unittest

from services import signature as sig


# اللي أحمد قاله بلسانه، بتاريخه.
AHMED_SAID = {
    "separate_genders": "2026-08-09",
    "palette_60_30_10": "2026-08-10",
}


class TestOriginIntegrity(unittest.TestCase):
    def test_only_ahmed_words_claim_ahmed_origin(self):
        got = {r["id"] for r in sig.RULES if r.get("origin") == sig.AHMED}
        self.assertEqual(got, set(AHMED_SAID),
                         "قاعدة بتدّعي إن أحمد قالها وهو مقالهاش")

    def test_ahmed_rules_carry_capture_date(self):
        for r in sig.RULES:
            if r.get("origin") == sig.AHMED:
                self.assertEqual(r.get("captured"), AHMED_SAID[r["id"]])

    def test_every_rule_has_known_origin(self):
        for r in sig.RULES:
            self.assertIn(r.get("origin"), (sig.AHMED, sig.SEEDED), r["id"])


class TestRegistryShape(unittest.TestCase):
    REQUIRED = ("id", "category", "status", "origin", "text", "why", "applies_at")
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

    def test_active_returns_confirmed_only(self):
        for r in sig.active():
            self.assertEqual(r["status"], sig.CONFIRMED)

    def test_by_stage_filters(self):
        got = sig.by_stage("lighting")
        self.assertTrue(got)
        for r in got:
            self.assertEqual(r["applies_at"], "lighting")


class TestFormatting(unittest.TestCase):
    def setUp(self):
        self.text = sig.format_signature()

    def test_ahmed_rule_is_marked(self):
        self.assertIn(sig.get("separate_genders")["text"], self.text)
        self.assertIn("🖋️", self.text)

    def test_counts_ahmed_rules_separately(self):
        self.assertIn("من كلامك", self.text)

    def test_ids_shown_for_editing(self):
        self.assertIn("[main_corridor_90]", self.text)

    def test_every_rule_appears(self):
        for r in sig.active():
            self.assertIn(r["text"], self.text, r["id"])


if __name__ == "__main__":
    unittest.main()
