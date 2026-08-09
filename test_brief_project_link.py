# -*- coding: utf-8 -*-
"""
اختبارات ربط البريف بمشروع -- صفر شبكة وصفر إنتاج.

الحارس الأساسي هنا مبدأ أحمد (2026-08-09): **آدم بيربط، مش بيعمل مشاريع.**
المشروع بيتولد في BAHR OS وبس. لو الكود بقى ينشئ مشروع عند الربط، الاختبارات
دي بتحمرّ.
"""

import unittest
from unittest.mock import MagicMock, patch

from services import client_briefs_service as svc


def _row(session, created, project=None, final=True):
    return {
        "id": f"id-{session}", "session_id": session, "created_at": created,
        "is_final": final, "project_id": project, "status": "new",
        "client_name": "عميل", "phone": None, "unit_location": None,
        "answers": {"الاسم": "عميل"},
    }


def _mock_client(rows):
    client = MagicMock()
    chain = client.table.return_value
    for m in ("select", "eq", "is_", "order", "limit", "update"):
        getattr(chain, m).return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    return client


class TestLinkContract(unittest.TestCase):
    """عقد الكتابة: True عند النجاح، False عند الفشل أو غياب اتصال."""

    def test_no_client_false(self):
        with patch.object(svc.supabase_service, "supabase_client", None):
            self.assertFalse(svc.link_session_to_project("s1", "PRJ-1"))

    def test_missing_session_false(self):
        with patch.object(svc.supabase_service, "supabase_client", _mock_client([])):
            self.assertFalse(svc.link_session_to_project(None, "PRJ-1"))

    def test_missing_project_false(self):
        """ربط ببروجيكت فاضي مرفوض -- مفيش ربط بمجهول."""
        with patch.object(svc.supabase_service, "supabase_client", _mock_client([])):
            self.assertFalse(svc.link_session_to_project("s1", None))
            self.assertFalse(svc.link_session_to_project("s1", ""))

    def test_success_true(self):
        with patch.object(svc.supabase_service, "supabase_client", _mock_client([])):
            self.assertTrue(svc.link_session_to_project("s1", "PRJ-MRE9OHLK"))

    def test_error_false(self):
        c = _mock_client([])
        c.table.return_value.execute.side_effect = RuntimeError("boom")
        with patch.object(svc.supabase_service, "supabase_client", c):
            self.assertFalse(svc.link_session_to_project("s1", "PRJ-1"))


class TestLinkWritesOnlyProjectId(unittest.TestCase):
    """آدم بيوسم البريف وبس -- عمرها ما تلمس أي جدول مشاريع."""

    def test_update_payload_is_project_id_only(self):
        c = _mock_client([])
        with patch.object(svc.supabase_service, "supabase_client", c):
            svc.link_session_to_project("s1", "PRJ-MRE9OHLK")
        payload = c.table.return_value.update.call_args[0][0]
        self.assertEqual(payload, {"project_id": "PRJ-MRE9OHLK"})

    def test_writes_to_briefs_table_only(self):
        c = _mock_client([])
        with patch.object(svc.supabase_service, "supabase_client", c):
            svc.link_session_to_project("s1", "PRJ-1")
        tables = {call.args[0] for call in c.table.call_args_list}
        self.assertEqual(tables, {svc.CLIENT_BRIEFS_TABLE})


class TestUnlinkedListing(unittest.TestCase):
    def test_no_client_none(self):
        with patch.object(svc.supabase_service, "supabase_client", None):
            self.assertIsNone(svc.list_unlinked_briefs())

    def test_error_none(self):
        c = _mock_client([])
        c.table.return_value.execute.side_effect = RuntimeError("boom")
        with patch.object(svc.supabase_service, "supabase_client", c):
            self.assertIsNone(svc.list_unlinked_briefs())

    def test_empty_is_list_not_none(self):
        with patch.object(svc.supabase_service, "supabase_client", _mock_client([])):
            self.assertEqual(svc.list_unlinked_briefs(), [])

    def test_dedupes_by_session(self):
        rows = [
            _row("s1", "2026-08-09T12:05:00Z"),
            _row("s1", "2026-08-09T12:00:00Z"),
            _row("s2", "2026-08-09T11:00:00Z"),
        ]
        with patch.object(svc.supabase_service, "supabase_client", _mock_client(rows)):
            self.assertEqual(len(svc.list_unlinked_briefs()), 2)


class TestAdamNeverCreatesProjects(unittest.TestCase):
    """الحارس المبدئي: مفيش أي كتابة لمشروع في مسار الربط."""

    def test_module_has_no_project_creation(self):
        import inspect
        src = inspect.getsource(svc)
        for forbidden in ("collection(\"projects\")", "collection('projects')",
                          "table(\"projects\")", "table('projects')"):
            self.assertNotIn(forbidden, src,
                             "آدم بيكتب في المشاريع — ده خرق لقرار أحمد")

    def test_module_does_not_import_firebase(self):
        """فحص الاستيرادات الحقيقية مش النص الخام.

        أول نسخة من الاختبار ده كانت بتـgrep على المصدر، فوقعت على تعليق
        بيقول "صفر استيراد من firebase_service" -- الاختبار مسك الجملة
        اللي بتشرحه. الفحص البنيوي بالـ ast مبيغلطش الغلطة دي.
        """
        import ast, inspect
        tree = ast.parse(inspect.getsource(svc))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(f"{node.module}.{a.name}" for a in node.names)
        firebase = [m for m in imported if "firebase" in m]
        self.assertEqual(firebase, [],
                         "طبقة البريفات لازم تفضل Supabase صافية")


if __name__ == "__main__":
    unittest.main()
