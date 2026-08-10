# -*- coding: utf-8 -*-
"""
Tests First -- حارس الوجود في أدوات التحديث (أوديت 2026-08-04).

نفس فئة باگ estProjectCode بتاع Bahr OS، بس جوه آدم: تحديث بمعرّف من
الموديل عبر .set(merge=True) بينشئ مستند وهمي لو المعرّف مش موجود.
الدليل الحي وقت الأوديت: مستند اسمه 'محمد علي' في client_followups
فيه حقول تحديث بس ومفيهوش أي حقول إنشاء.

الاختبارات على الدوال الـ pure للحارس -- صفر Firestore وصفر LLM.
"""


class _WriteRecorder:
    """عميل Supabase مزوّر بيسجّل أي كتابة بدل ما ينفّذها.

    الغرض إثبات **إن الكتابة ماحصلتش** عند الرفض -- رسالة رفض من غير
    إثبات إن القاعدة ماتلمستش مش كفاية.
    """

    def __init__(self, calls):
        self._calls = calls

    def table(self, name):
        self._table = name
        return self

    def update(self, payload):
        self._calls.append((self._table, payload))
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": []})()


def run_test(name, fn):
    try:
        fn()
        print(f"OK  {name}")
        return True
    except AssertionError as e:
        print(f"FAIL {name}: {e}")
        return False
    except Exception as e:
        print(f"FAIL {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    from services.update_guard import missing_document_message

    results = []

    def missing_id_is_refused_with_available_list():
        msg = missing_document_message(
            "مشروع", "PRJ-WRONG", ["PRJ-MRWMHQAR", "PRJ-MRE9OHLK"]
        )
        assert msg is not None
        assert "PRJ-WRONG" in msg and "مش موجود" in msg
        assert "PRJ-MRWMHQAR" in msg and "PRJ-MRE9OHLK" in msg, msg
        assert "اتعمل" not in msg, "الرسالة ماتقولش إن حاجة اتعملت"

    def empty_available_list_still_refuses():
        msg = missing_document_message("عميل", "CLT-X", [])
        assert msg is not None and "مفيش" in msg, msg

    def long_lists_are_truncated_not_dumped():
        many = [f"PRJ-{i:04d}" for i in range(50)]
        msg = missing_document_message("مشروع", "PRJ-NOPE", many)
        assert len(msg) < 700, f"الرسالة طويلة جدًا ({len(msg)})"
        assert "..." in msg or "وغيرهم" in msg, msg

    def guard_is_wired_into_every_phantom_path():
        # مسارات Firestore اللي لسه بتكتب بمعرّف من الموديل عبر set(merge=True)
        src = open("services/claude_service.py", encoding="utf-8").read()
        for marker in ("update_client_followup",):
            idx = src.index('tool_name == "' + marker + '"')
            block = src[idx:idx + 2500]
            assert "missing_document_message" in block, marker + " من غير حارس"
            assert "document_exists" in block, marker + " مش بيفحص الوجود"

    def the_supabase_project_path_keeps_the_same_guarantee():
        """مسار المشاريع اتنقل لـSupabase -- والضمانة لازم تنتقل معاه.

        قبل 2026-08-10 كان الحارس `document_exists` بتاع Firestore، وكان
        بيتفحص هنا بالنص. الكتابة بقت `supabase_store.update_project_adam_fields`،
        فالفحص النصي القديم بقى بيدوّر على آلية مش موجودة -- وده هيخلي
        الاختبار أحمر رغم إن الضمانة اتحفظت.

        الضمانة نفسها مش بتتغيّر: **معرّف مش موجود مايكتبش حاجة**، ولازم
        يرد برسالة فيها البدائل. وفيه حالة تالتة أضيفت هنا وماكانتش موجودة
        في نسخة Firestore: لو مقدرناش نقرا أصلاً، الرد لا بيكتب ولا بيدّعي
        إن المشروع مش موجود -- لأن الاتنين كذب.
        """
        from fake_firestore import use_fake_firestore
        from services import supabase_store

        original_exists = supabase_store.project_exists
        original_client = supabase_store._client
        calls = []
        supabase_store._client = lambda: _WriteRecorder(calls)
        try:
            # (1) المشروع مش موجود -> مفيش كتابة + البدائل في الرسالة
            supabase_store.project_exists = lambda pid: False
            supabase_store.list_project_ids = lambda limit=30: ["PRJ-AAA", "PRJ-BBB"]
            ok, msg = supabase_store.update_project_adam_fields(
                "PRJ-GHALAT", {"status": "delayed"}
            )
            assert ok is False, "كتب على معرّف مش موجود"
            assert not calls, "لمس القاعدة رغم إن المعرّف غلط: " + str(calls)
            assert "PRJ-AAA" in msg, "الرسالة مفيهاش البدائل: " + msg

            # (2) مقدرناش نتأكد -> ممنوع نكتب وممنوع نقول "مش موجود"
            supabase_store.project_exists = lambda pid: None
            ok, msg = supabase_store.update_project_adam_fields(
                "PRJ-AAA", {"status": "delayed"}
            )
            assert ok is False and not calls, "كتب وهو مش متأكد: " + str(calls)
            # تأكيد **إيجابي** بالقصد. أول نسخة كانت `"مش موجود" not in msg`
            # وطلعت فاضية: رسالة "مش موجود" الحقيقية بتقول "مفيش مشروع
            # بالمعرّف"، فالنص ده مكانش بيظهر أصلاً والتأكيد كان بيعدي مهما
            # حصل. اتمسك بالتحوير -- شيل الفرع ده وشوف الاختبار بيحمرّ ولا لأ.
            assert "مش قادر أتأكد" in msg, (
                "لازم يقول إنه مش قادر يتأكد، مش يحكم بالغياب: " + msg
            )
            assert "مفيش مشروع" not in msg, "حكم بالغياب وهو مش قادر يقرا: " + msg

            # (3) موجود -> الكتابة بتحصل فعلاً
            supabase_store.project_exists = lambda pid: True
            ok, msg = supabase_store.update_project_adam_fields(
                "PRJ-AAA", {"status": "delayed"}
            )
            assert ok is True, "مكتبش على مشروع موجود: " + msg
            assert calls, "قال تم وهو مالمسش القاعدة"
        finally:
            supabase_store.project_exists = original_exists
            supabase_store._client = original_client

    def adam_cannot_write_bahr_os_columns():
        """أعمدة الهوية بتترفض برسالة، مش بتتجاهَل في صمت.

        التجاهل الصامت أخطر من الرفض: أحمد بيقول "غيّر المساحة لـ200"،
        وآدم بيرد "تم" وهو كتب حاجة تانية أو مكتبش حاجة.
        """
        from services import supabase_store

        original_client = supabase_store._client
        calls = []
        supabase_store._client = lambda: _WriteRecorder(calls)
        try:
            for column in ("client", "area", "name", "level", "allowed_supervisors"):
                ok, msg = supabase_store.update_project_adam_fields(
                    "PRJ-AAA", {column: "قيمة"}
                )
                assert ok is False, column + " اتقبل رغم إنه عمود BAHR OS"
                assert column in msg, "الرسالة مبتقولش الحقل المرفوض: " + msg
                assert "BAHR OS" in msg, "الرسالة مبتوجّهش لمكان التعديل: " + msg
            assert not calls, "لمس القاعدة رغم الرفض: " + str(calls)
        finally:
            supabase_store._client = original_client

    def no_unguarded_merge_writes_remain():
        # أي set(merge=True) على مجموعة بمعرّف خارجي لازم يبقى محروس
        import re
        for path in ("services/claude_service.py", "services/firebase_service.py"):
            src = open(path, encoding="utf-8").read()
            # الكتابة بـ merge بس -- الإنشاء الصريح بمعرّف مولّد داخليًا
            # (uuid) مسار سليم ومش محتاج حارس
            for m in re.finditer(r'collection\("(projects|client_followups)"\)'
                                 r'\.document\(([a-z_]+)\)\.set\([^\n]*merge', src):
                window = src[max(0, m.start() - 900):m.start()]
                assert "document_exists" in window, (
                    f"{path}: كتابة من غير حارس على {m.group(1)} بمعرّف {m.group(2)}"
                )

    for name, fn in [
        ("المعرّف الغلط بيترفض وبتتعرض البدائل", missing_id_is_refused_with_available_list),
        ("مفيش بدائل = رفض برضه", empty_available_list_still_refuses),
        ("القوايم الطويلة بتتقص", long_lists_are_truncated_not_dumped),
        ("الحارس موصّل في مسارات Firestore الباقية", guard_is_wired_into_every_phantom_path),
        ("مفيش كتابة merge من غير حارس", no_unguarded_merge_writes_remain),
        ("مسار المشاريع في Supabase محافظ على نفس الضمانة", the_supabase_project_path_keeps_the_same_guarantee),
        ("آدم مش قادر يكتب أعمدة BAHR OS", adam_cannot_write_bahr_os_columns),
    ]:
        results.append(run_test(name, fn))

    print()
    if all(results):
        print(f"{len(results)}/{len(results)} اختبار عدّى")
    else:
        print(f"{sum(results)}/{len(results)} بس اللي عدّى")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
