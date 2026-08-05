# -*- coding: utf-8 -*-
"""
حارس القاعدة: **أي اختبار بيلمس Firestore لازم يبقى mock من الأول.**

القاعدة اتحطت في 2026-08-05 بعد حادثة حقيقية: `test_loan_commands.py` كان
بيكتب حدثين في `adam_events` بتاع الإنتاج عند كل تشغيلة. الحدثين دول كانوا
بيمنعوا تلات اختبارات تانية من الشغل أصلاً (بيشترطوا سجل نضيف على نفس
الكيان)، وبيسيبوا أثر دائم في سجل append-only.

الملف ده بيفحص سورس كل ملفات test_*.py ويرفض أي واحد بيفتح اتصال حقيقي.
لو ضفت اختبار جديد بيحتاج Firestore -- استخدم fake_firestore، مش init_firebase.
"""

import pathlib
import re

ALLOWED = {
    # الملف ده نفسه بيقرا سورس الاختبارات، فبيحتوي على الأسماء نصًا
    "test_no_production_writes.py": "بيفحص السورس، مش بينفذ",
}

# ============================================================
# دين متبقّي -- اختبارات لسه بتلمس الإنتاج (2026-08-05)
# ============================================================
# القاعدة اتحطت بعد ما اتصلحت اختبارات الأقساط الأربعة. الحارس كشف إن فيه
# 11 اختبار تاني على نفس النمط، ودول من قبل القاعدة.
#
# الليستة دي **سقف مش أرضية**: أي اختبار جديد بيلمس Firestore هيفشل هنا
# فورًا، والليستة المفروض تقصر مع الوقت لحد ما تفضى -- ممنوع تكبر.
#
# اللي اتحوّل خلاص: test_loan_commands, test_loan_conflict_observer,
# test_conflict_resolution_flow, test_tracking_stability, test_memory.
KNOWN_UNMIGRATED = {
    "test_companionship_layer.py",
    "test_event_store.py",
    "test_pipeline_integration.py",
    "test_self_diagnosis.py",
    "test_self_state_core.py",
    "test_self_state_engine.py",
    "test_tool_health.py",
    "test_tool_lifecycle_diagnostics.py",
    "test_tool_registration_guard.py",
    "test_verified_expression.py",
}

FORBIDDEN_PATTERNS = [
    (re.compile(r"^\s*from services\.firebase_service import.*\binit_firebase\b", re.M),
     "بيستورد init_firebase -- ده بيفتح اتصال حقيقي بالإنتاج"),
    (re.compile(r"^\s*init_firebase\s*\(", re.M),
     "بينادي init_firebase() -- استخدم fake_firestore بدالها"),
]


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
    root = pathlib.Path(__file__).parent
    test_files = sorted(root.glob("test_*.py"))

    results = []

    def _scan():
        """بيرجع أسماء الاختبارات اللي بتفتح اتصال إنتاج حقيقي."""
        found = set()
        for path in test_files:
            if path.name in ALLOWED:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            for pattern, _why in FORBIDDEN_PATTERNS:
                if pattern.search(source):
                    found.add(path.name)
                    break
        return found

    def no_new_test_opens_a_real_connection():
        """الحارس الأساسي: ممنوع أي اختبار **جديد** يلمس الإنتاج."""
        new_offenders = sorted(_scan() - KNOWN_UNMIGRATED)
        assert not new_offenders, (
            "اختبارات جديدة بتلمس Firestore الحقيقي -- استخدم fake_firestore:\n  - "
            + "\n  - ".join(new_offenders)
        )

    def the_debt_list_only_shrinks():
        """أي اسم اتحوّل لازم يتشال من الليستة، وإلا الليستة بتكدب."""
        stale = sorted(KNOWN_UNMIGRATED - _scan())
        assert not stale, (
            "دول بقوا نضاف -- شيلهم من KNOWN_UNMIGRATED:\n  - " + "\n  - ".join(stale)
        )

    def the_migrated_loan_tests_stay_migrated():
        """الأربعة اللي اتصلحوا في 2026-08-05 ممنوع يرجعوا يلمسوا الإنتاج."""
        migrated = {
            "test_loan_commands.py", "test_loan_conflict_observer.py",
            "test_conflict_resolution_flow.py", "test_tracking_stability.py",
        }
        regressed = sorted(migrated & _scan())
        assert not regressed, "رجعوا يلمسوا الإنتاج تاني:\n  - " + "\n  - ".join(regressed)

    def the_fake_is_actually_available():
        from fake_firestore import FakeFirestore, install_fake_firestore, use_fake_firestore
        assert callable(install_fake_firestore) and callable(use_fake_firestore)
        assert FakeFirestore() is not None

    def the_fake_never_leaks_into_the_real_module():
        """use_fake_firestore لازم يرجّع الأصلي حتى لو الجوه رمى استثناء."""
        import services.firebase_service as firebase_service
        from fake_firestore import use_fake_firestore

        before = firebase_service.firestore_db
        try:
            with use_fake_firestore():
                assert firebase_service.firestore_db is not before
                raise RuntimeError("انفجار مقصود")
        except RuntimeError:
            pass
        assert firebase_service.firestore_db is before, "الـ fake فضل مركّب بعد الخروج!"

    def the_fake_supports_what_the_event_store_needs():
        """أي نقص في الـ fake بيظهر هنا مش وسط اختبار تاني."""
        from fake_firestore import use_fake_firestore
        from services import event_store

        with use_fake_firestore() as db:
            first = event_store.record_event(
                entity_type="probe", entity_id="e1", attribute="state",
                new_value="a", source="test", actor="guard",
            )
            event_store.record_event_with_write(
                entity_type="probe", entity_id="e1", attribute="state",
                domain_collection="probe_domain", domain_document="doc",
                domain_data={"nested": {"value": 1}},
                new_value="b", previous_value="a", source="test", actor="guard",
            )
            events = event_store.get_events_for_entity("probe", "e1")
            assert len(events) == 2, events
            assert events[0]["event_id"] == first
            assert events[-1]["new_value"] == "b", "الترتيب الزمني غلط"
            assert db.all_docs("probe_domain")["doc"] == {"nested": {"value": 1}}

            fetched = event_store.get_event(first)
            assert fetched["attribute"] == "state"

    def the_fake_merges_like_firestore():
        from fake_firestore import FakeFirestore

        db = FakeFirestore()
        db.collection("c").document("d").set({"paid": {"a": True}})
        db.collection("c").document("d").set({"paid": {"b": False}}, merge=True)
        stored = db.collection("c").document("d").get().to_dict()
        assert stored["paid"] == {"a": True, "b": False}, stored

        db.collection("c").document("d").set({"paid": {"c": 1}}, merge=False)
        assert db.collection("c").document("d").get().to_dict()["paid"] == {"c": 1}

    def the_fake_generates_auto_ids():
        """document() من غير معرّف بيولّد واحد -- الكود بيستخدمها في الملاحظات."""
        from fake_firestore import FakeFirestore

        db = FakeFirestore()
        db.collection("notes").document().set({"text": "أولى"})
        db.collection("notes").document().set({"text": "تانية"})
        assert db.count("notes") == 2, "المعرّفات التلقائية اتصادمت"

        _, ref = db.collection("notes").add({"text": "تالتة"})
        assert db.count("notes") == 3 and ref.get().to_dict()["text"] == "تالتة"

    def the_fake_batch_is_atomic():
        from fake_firestore import FakeFirestore

        db = FakeFirestore()
        batch = db.batch()
        batch.set(db.collection("x").document("1"), {"v": 1})
        batch.set(db.collection("y").document("2"), {"v": 2})
        assert db.count("x") == 0 and db.count("y") == 0, "اتكتب قبل الـ commit!"
        batch.commit()
        assert db.count("x") == 1 and db.count("y") == 1

    for name, fn in [
        ("ولا اختبار جديد بيلمس الإنتاج (الحارس الأساسي)", no_new_test_opens_a_real_connection),
        ("ليستة الدين بتقصر مش بتكبر", the_debt_list_only_shrinks),
        ("اختبارات الأقساط الأربعة فضلت متحوّلة", the_migrated_loan_tests_stay_migrated),
        ("fake_firestore متاح وشغال", the_fake_is_actually_available),
        ("الـ fake بيترفع حتى لو حصل استثناء", the_fake_never_leaks_into_the_real_module),
        ("الـ fake بيغطي كل اللي event_store محتاجه", the_fake_supports_what_the_event_store_needs),
        ("الـ fake بيدمج زي Firestore بالظبط", the_fake_merges_like_firestore),
        ("الـ fake بيولّد معرّفات تلقائية", the_fake_generates_auto_ids),
        ("الـ batch بتاع الـ fake ذري فعلاً", the_fake_batch_is_atomic),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
