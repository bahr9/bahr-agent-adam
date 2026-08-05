# -*- coding: utf-8 -*-
"""
تحقق من حفظ ملاحظات الذاكرة (save_memory_note).

قاعدة الاختبارات (2026-08-05): الملف ده كان 4 سطور من غير أي assert --
مجرد سكريبت بينادي save_memory_note على الإنتاج ويطبع النتيجة. كل تشغيلة
كانت بتسيب ملاحظة زبالة بـ user_id='test_user' في memory_notes (اتلقى منها
4 وقت الأوديت). دلوقتي بيشتغل على fake_firestore وبيتحقق فعلاً من اللي اتكتب.
"""

from fake_firestore import install_fake_firestore


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
    db = install_fake_firestore()
    from services.firebase_service import save_memory_note, MEMORY_NOTES_COLLECTION

    def notes_for(user_id):
        return [
            n for n in db.all_docs(MEMORY_NOTES_COLLECTION).values()
            if n.get("user_id") == user_id
        ]

    results = []

    def saving_a_note_reports_success():
        assert save_memory_note("u1", "أحمد بيفضّل الرد المختصر", "تفضيلات", "أحمد")

    def the_note_is_actually_written():
        save_memory_note("u2", "ميعاد تسليم مشروع البحر", "مواعيد", "بحر")
        notes = notes_for("u2")
        assert len(notes) == 1, f"المفروض ملاحظة واحدة، لقيت {len(notes)}"
        assert notes[0]["text"] == "ميعاد تسليم مشروع البحر", notes[0]
        assert notes[0]["category"] == "مواعيد", notes[0]
        assert notes[0]["related_to"] == "بحر", notes[0]

    def every_note_carries_a_timestamp():
        save_memory_note("u3", "ملاحظة بتوقيت", "عام", "")
        note = notes_for("u3")[0]
        assert note.get("created_at"), "مفيش created_at"
        assert note.get("timestamp_str"), "مفيش timestamp_str"

    def notes_are_kept_per_user():
        before = len(db.all_docs(MEMORY_NOTES_COLLECTION))
        save_memory_note("u4", "ملاحظة أولى", "عام", "")
        save_memory_note("u5", "ملاحظة تانية", "عام", "")
        after = db.all_docs(MEMORY_NOTES_COLLECTION)
        assert len(after) == before + 2, f"{before} -> {len(after)}"
        assert len(notes_for("u4")) == 1 and len(notes_for("u5")) == 1

    def arabic_text_survives_the_round_trip():
        save_memory_note("u6", "نص عربي فيه تشكيل وأرقام ١٢٣", "عام", "")
        assert notes_for("u6")[0]["text"] == "نص عربي فيه تشكيل وأرقام ١٢٣"

    for name, fn in [
        ("حفظ ملاحظة بيرجّع نجاح", saving_a_note_reports_success),
        ("الملاحظة بتتكتب فعلاً بكل حقولها", the_note_is_actually_written),
        ("كل ملاحظة شايلة وقتها", every_note_carries_a_timestamp),
        ("الملاحظات بتتحفظ لكل مستخدم لوحده", notes_are_kept_per_user),
        ("النص العربي بيرجع زي ما هو", arabic_text_survives_the_round_trip),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    print("\nكل ده على fake_firestore -- ولا ملاحظة اتكتبت في الإنتاج.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
