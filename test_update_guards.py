# -*- coding: utf-8 -*-
"""
Tests First -- حارس الوجود في أدوات التحديث (أوديت 2026-08-04).

نفس فئة باگ estProjectCode بتاع Bahr OS، بس جوه آدم: تحديث بمعرّف من
الموديل عبر .set(merge=True) بينشئ مستند وهمي لو المعرّف مش موجود.
الدليل الحي وقت الأوديت: مستند اسمه 'محمد علي' في client_followups
فيه حقول تحديث بس ومفيهوش أي حقول إنشاء.

الاختبارات على الدوال الـ pure للحارس -- صفر Firestore وصفر LLM.
"""


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
        # التلات مسارات اللي بيكتبوا بمعرّف من الموديل عبر set(merge=True)
        src = open("services/claude_service.py", encoding="utf-8").read()
        for marker in ("update_project_status", "update_client_followup"):
            idx = src.index('tool_name == "' + marker + '"')
            block = src[idx:idx + 2500]
            assert "missing_document_message" in block, marker + " من غير حارس"
            assert "document_exists" in block, marker + " مش بيفحص الوجود"

        fb_src = open("services/firebase_service.py", encoding="utf-8").read()
        idx = fb_src.index("def update_bahr_project")
        block = fb_src[idx:idx + 1500]
        assert "document_exists" in block, "update_bahr_project من غير حارس"
        assert block.index("document_exists") < block.index(".set(update_data"), (
            "الحارس لازم يسبق الكتابة"
        )

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
        ("الحارس موصّل في التلات مسارات", guard_is_wired_into_every_phantom_path),
        ("مفيش كتابة merge من غير حارس", no_unguarded_merge_writes_remain),
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
