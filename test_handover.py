# -*- coding: utf-8 -*-
"""
اختبارات محضر التسليم -- محلي بالكامل، صفر شبكة.

القاعدة اللي بتحرسها (أحمد 2026-08-10): القاعدة المكسورة تتسجل بمين
اقترح ومين وافق. والتسجيل مايتكررش مع كل تشغيلة.
"""

import unittest
from unittest.mock import MagicMock, patch

from services import handover_service as hs


YIELD = {"material": "نحاس مطفي", "rule_id": "brass_not_steel",
         "rule": "النحاس المطفي بدل الاستانلس", "ban": "دهبي وفضي لامع"}


class TestMerge(unittest.TestCase):
    def test_records_attribution(self):
        out, added = hs.merge_waivers([], [YIELD])
        self.assertEqual(added, 1)
        self.assertEqual(out[0]["proposed_by"], "أحمد")
        self.assertEqual(out[0]["agreed_by"], "العميل")
        self.assertEqual(out[0]["gave_up"], "نحاس مطفي")
        self.assertEqual(out[0]["because"], "دهبي وفضي لامع")
        self.assertTrue(out[0]["at"])

    def test_no_duplicate_on_rerun(self):
        first, _ = hs.merge_waivers([], [YIELD])
        second, added = hs.merge_waivers(first, [YIELD])
        self.assertEqual(added, 0)
        self.assertEqual(len(second), 1)

    def test_keeps_existing_and_adds_new(self):
        first, _ = hs.merge_waivers([], [YIELD])
        other = dict(YIELD, material="سقف معلق", rule_id="no_full_drop_ceiling")
        out, added = hs.merge_waivers(first, [other])
        self.assertEqual(added, 1)
        self.assertEqual(len(out), 2)

    def test_empty_yields_change_nothing(self):
        out, added = hs.merge_waivers([{"rule": "x", "gave_up": "y"}], [])
        self.assertEqual(added, 0)
        self.assertEqual(len(out), 1)


class TestRecordContract(unittest.TestCase):
    def _client(self):
        c = MagicMock()
        chain = c.table.return_value
        for m in ("update", "eq"):
            getattr(chain, m).return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        return c

    def test_no_client_returns_zero(self):
        with patch.object(hs.supabase_service, "supabase_client", None):
            self.assertEqual(hs.record_yields("s1", [], [YIELD]), 0)

    def test_writes_only_waivers(self):
        c = self._client()
        with patch.object(hs.supabase_service, "supabase_client", c):
            hs.record_yields("s1", [], [YIELD])
        payload = c.table.return_value.update.call_args[0][0]
        self.assertEqual(list(payload.keys()), ["waivers"])

    def test_error_returns_zero_not_raise(self):
        c = self._client()
        c.table.return_value.execute.side_effect = RuntimeError("boom")
        with patch.object(hs.supabase_service, "supabase_client", c):
            self.assertEqual(hs.record_yields("s1", [], [YIELD]), 0)

    def test_skips_write_when_nothing_new(self):
        first, _ = hs.merge_waivers([], [YIELD])
        c = self._client()
        with patch.object(hs.supabase_service, "supabase_client", c):
            self.assertEqual(hs.record_yields("s1", first, [YIELD]), 0)
        c.table.return_value.update.assert_not_called()


class TestFormat(unittest.TestCase):
    def test_clean_project_says_so(self):
        text = hs.format_handover({"client_name": "منى", "waivers": []})
        self.assertIn("مفيش قاعدة اتكسرت", text)

    def test_lists_who_proposed_and_who_agreed(self):
        w, _ = hs.merge_waivers([], [YIELD])
        text = hs.format_handover({"client_name": "منى", "waivers": w})
        self.assertIn("اقترحها: أحمد", text)
        self.assertIn("وافق: العميل", text)
        self.assertIn("نحاس مطفي", text)
        self.assertIn("دهبي وفضي لامع", text)

    def test_shows_project_link_state(self):
        text = hs.format_handover({"client_name": "منى", "waivers": []})
        self.assertIn("مش مربوط بمشروع", text)
        text2 = hs.format_handover({"client_name": "منى", "waivers": [],
                                    "project_id": "PRJ-1"})
        self.assertIn("PRJ-1", text2)

    def test_no_crash_on_empty_row(self):
        self.assertIn("محضر التسليم", hs.format_handover({}))


class TestObjections(unittest.TestCase):
    """العرض بيطلب من العميل يعترض بالاسم -- المحضر لازم يشوف الرد."""

    OPEN = {"said": "الأخضر تقيل", "did": "", "at": "2026-08-10T10:00:00Z"}
    CLOSED = {"said": "الأرضية غامقة", "did": "فتّحناها درجتين",
              "at": "2026-08-10T11:00:00Z"}

    def test_silent_when_no_objections(self):
        text = hs.format_handover({"client_name": "منى", "waivers": []})
        self.assertNotIn("رد العميل", text)

    def test_quotes_the_client_and_our_answer(self):
        text = hs.format_handover({"client_name": "منى", "objections": [self.CLOSED]})
        self.assertIn("الأرضية غامقة", text)
        self.assertIn("فتّحناها درجتين", text)

    def test_open_objection_blocks_a_clean_close(self):
        text = hs.format_handover({"client_name": "منى", "objections": [self.OPEN]})
        self.assertIn("لسه مردّيناش", text)
        self.assertIn("المشروع مايتقفلش", text)

    def test_no_warning_when_all_answered(self):
        text = hs.format_handover({"client_name": "منى", "objections": [self.CLOSED]})
        self.assertNotIn("مايتقفلش", text)

    def test_whitespace_only_answer_counts_as_open(self):
        o = dict(self.CLOSED, did="   ")
        text = hs.format_handover({"client_name": "منى", "objections": [o]})
        self.assertIn("لسه مردّيناش", text)

    def test_objections_show_even_with_clean_waivers(self):
        text = hs.format_handover({"client_name": "منى", "waivers": [],
                                   "objections": [self.CLOSED]})
        self.assertIn("مفيش قاعدة اتكسرت", text)
        self.assertIn("الأرضية غامقة", text)



class TestApprovals(unittest.TestCase):
    """قاعدة أحمد (2026-08-10): كل مرحلة بمستند أبروفد."""

    OK = {"stage": "proposal", "how": "واتساب", "at": "2026-08-10T10:00:00Z"}

    def test_all_four_stages_are_listed(self):
        text = hs.format_handover({"client_name": "منى"})
        for _, label in hs.STAGES:
            self.assertIn(label, text)

    def test_missing_approvals_are_named_not_just_counted(self):
        text = hs.format_handover({"client_name": "منى"})
        self.assertIn("مفيش اعتماد متسجل", text)
        self.assertIn("عدّت من غير توقيع", text)

    def test_recorded_approval_shows_how_and_when(self):
        text = hs.format_handover({"client_name": "منى", "approvals": [self.OK]})
        self.assertIn("✅ العرض الأول — واتساب", text)
        self.assertIn("2026-08-10", text)

    def test_full_approval_drops_the_warning(self):
        rows = [dict(self.OK, stage=k) for k, _ in hs.STAGES]
        text = hs.format_handover({"client_name": "منى", "approvals": rows})
        self.assertNotIn("عدّت من غير توقيع", text)

    def test_approval_without_how_does_not_crash(self):
        text = hs.format_handover({"client_name": "منى",
                                   "approvals": [{"stage": "brief"}]})
        self.assertIn("✅ الاستبيان", text)


if __name__ == "__main__":
    unittest.main()
