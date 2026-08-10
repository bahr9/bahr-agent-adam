# -*- coding: utf-8 -*-
"""
اختبارات خدمة استبيانات العملاء -- صفر شبكة وصفر إنتاج.

الـ Supabase client متزيف بالكامل (قاعدة البيت: الاختبارات عمرها
ما تلمس إنتاج، والموك من أول سطر مش بعد ما نجرب).
"""

import unittest
from unittest.mock import MagicMock, patch

from services import client_briefs_service as svc


def _row(session, created, final=False, answers=None, **extra):
    row = {
        "id": f"id-{session}-{created}",
        "session_id": session,
        "created_at": created,
        "is_final": final,
        "client_name": extra.get("client_name"),
        "phone": extra.get("phone"),
        "unit_location": extra.get("unit_location"),
        "status": "new",
        "answers": answers or {},
    }
    row.update(extra)
    return row


def _mock_client_returning(rows):
    """موك بيرد على سلسلة table().select()...execute() بصفوف محددة."""
    client = MagicMock()
    chain = client.table.return_value
    for m in ("select", "eq", "order", "limit", "update"):
        getattr(chain, m).return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    return client


class TestDedupeLatest(unittest.TestCase):
    """اللقطات المرحلية: أحدث لقطة لكل جلسة، والنهائية بتكسب."""

    def test_latest_snapshot_wins_per_session(self):
        # الصفوف مرتبة تنازليًا زي ما Supabase بيرجعها
        rows = [
            _row("s1", "2026-08-09T12:05:00Z", answers={"الاسم": "أحدث"}),
            _row("s1", "2026-08-09T12:00:00Z", answers={"الاسم": "أقدم"}),
        ]
        result = svc._dedupe_latest(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["answers"]["الاسم"], "أحدث")

    def test_final_beats_newer_partial(self):
        rows = [
            _row("s1", "2026-08-09T12:05:00Z", final=False),
            _row("s1", "2026-08-09T12:03:00Z", final=True),
        ]
        result = svc._dedupe_latest(rows)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["is_final"])

    def test_sessions_stay_separate(self):
        rows = [
            _row("s1", "2026-08-09T12:00:00Z"),
            _row("s2", "2026-08-09T11:00:00Z"),
        ]
        self.assertEqual(len(svc._dedupe_latest(rows)), 2)

    def test_row_without_session_is_its_own(self):
        rows = [
            _row(None, "2026-08-09T12:00:00Z"),
            _row(None, "2026-08-09T11:00:00Z"),
        ]
        self.assertEqual(len(svc._dedupe_latest(rows)), 2)


class TestListNewBriefs(unittest.TestCase):
    """عقد None: فشل/غياب اتصال = None، نجاح فاضي = []."""

    def test_no_client_returns_none(self):
        with patch.object(svc.supabase_service, "supabase_client", None):
            self.assertIsNone(svc.list_new_briefs())

    def test_query_error_returns_none(self):
        client = _mock_client_returning([])
        client.table.return_value.execute.side_effect = RuntimeError("boom")
        with patch.object(svc.supabase_service, "supabase_client", client):
            self.assertIsNone(svc.list_new_briefs())

    def test_empty_success_returns_empty_list(self):
        with patch.object(svc.supabase_service, "supabase_client",
                          _mock_client_returning([])):
            self.assertEqual(svc.list_new_briefs(), [])

    def test_success_dedupes(self):
        rows = [
            _row("s1", "2026-08-09T12:05:00Z"),
            _row("s1", "2026-08-09T12:00:00Z"),
            _row("s2", "2026-08-09T11:00:00Z", final=True),
        ]
        with patch.object(svc.supabase_service, "supabase_client",
                          _mock_client_returning(rows)):
            result = svc.list_new_briefs()
        self.assertEqual(len(result), 2)


class TestMarkSeen(unittest.TestCase):
    def test_no_client_false(self):
        with patch.object(svc.supabase_service, "supabase_client", None):
            self.assertFalse(svc.mark_session_seen("s1"))

    def test_no_session_false(self):
        with patch.object(svc.supabase_service, "supabase_client",
                          _mock_client_returning([])):
            self.assertFalse(svc.mark_session_seen(None))

    def test_success_true(self):
        with patch.object(svc.supabase_service, "supabase_client",
                          _mock_client_returning([])):
            self.assertTrue(svc.mark_session_seen("s1"))


class TestFormatBrief(unittest.TestCase):
    def test_partial_is_labeled(self):
        text = svc.format_brief(_row("s1", "2026-08-09T12:00:00Z", final=False,
                                     answers={"الاسم": "منى"}))
        self.assertIn("وقف في النص", text)

    def test_final_not_labeled_partial(self):
        text = svc.format_brief(_row("s1", "2026-08-09T12:00:00Z", final=True))
        self.assertNotIn("وقف في النص", text)

    def test_priority_fields_surface_first(self):
        answers = {
            "الميزانية": "800K",
            "ممنوعات": ["الرمادي البارد", "أسقف معقدة"],
            "مقاس السرير": "١٨٠ سم",
        }
        text = svc.format_brief(
            _row("s1", "2026-08-09T12:00:00Z", final=True, answers=answers,
                 client_name="منى", phone="0100"))
        self.assertIn("منى", text)
        self.assertIn("الميزانية: 800K", text)
        self.assertIn("الرمادي البارد، أسقف معقدة", text)
        # الميزانية (أولوية) لازم تظهر قبل مقاس السرير (باقي الإجابات)
        self.assertLess(text.index("الميزانية"), text.index("مقاس السرير"))

    def test_empty_answers_no_crash(self):
        text = svc.format_brief(_row("s1", "2026-08-09T12:00:00Z", final=True))
        self.assertIn("من غير اسم", text)


if __name__ == "__main__":
    unittest.main()


class TestFindBrief(unittest.TestCase):
    """البحث المشترك بين /direction و/moodboard."""

    A = {"session_id": "a1", "client_name": "إسراء محمد", "status": "new",
         "unit_location": "مدينتي", "answers": {}}
    B = {"session_id": "b2", "client_name": "كريم فؤاد", "status": "seen",
         "unit_location": "التجمع", "answers": {}}
    ARCH = {"session_id": "c3", "client_name": "هند سامي", "status": "archived",
            "unit_location": "الشيخ زايد", "answers": {}}

    def test_no_arg_takes_the_first_live_one(self):
        b, err = svc.find_brief("", [self.A, self.B])
        self.assertIsNone(err)
        self.assertEqual(b["session_id"], "a1")

    def test_archived_is_never_the_answer(self):
        b, err = svc.find_brief("", [self.ARCH])
        self.assertIsNone(b)
        self.assertIn("مفيش بريف", err)

    def test_finds_by_name(self):
        b, err = svc.find_brief("كريم", [self.A, self.B])
        self.assertEqual(b["session_id"], "b2")

    def test_finds_by_location(self):
        b, err = svc.find_brief("التجمع", [self.A, self.B])
        self.assertEqual(b["session_id"], "b2")

    def test_archived_hit_says_archived_not_missing(self):
        b, err = svc.find_brief("هند", [self.A, self.ARCH])
        self.assertIsNone(b)
        self.assertIn("مؤرشف", err)

    def test_ambiguous_asks_for_more_letters(self):
        two = [self.A, dict(self.B, client_name="إسراء علي", session_id="d4")]
        b, err = svc.find_brief("إسراء", two)
        self.assertIsNone(b)
        self.assertIn("زود حروف", err)

    def test_unknown_name_says_so(self):
        b, err = svc.find_brief("زيزو", [self.A])
        self.assertIsNone(b)
        self.assertIn("زيزو", err)
