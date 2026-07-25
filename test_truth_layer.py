# -*- coding: utf-8 -*-
"""
Tests First -- Phase 1 (Truth Layer، Architecture v2).
اتكتبت قبل أي سطر في services/truth_layer.py، بناءً على طلب صريح: صحة
الحساب المشتق (derived facts) لازم تتثبّت كـ Contract بالاختبار الأول،
مش تُفترض. التركيز الأساسي هنا على الاختبارين المطلوبين تحديدًا:

  1. derived fact صحيح (count == len(overdue_items)) -- لازم ينجح.
  2. derived fact غلط (count != len(overdue_items)) -- لازم يتكتشف ويفشل.

باقي الاختبارات بتثبت العقد الأساسي لباقي أنواع المصادر (event_evidence,
static_schedule) والـ enum -- ده كله جزء من نفس التصميم (v2)، مش اختبارات
منفصلة عنه.

لا يحتاج Firestore -- بنية بيانات وتحقق منطقي بحت (Unit Tests).
"""

import time
from datetime import timedelta


def run_test(name, fn):
    try:
        fn()
        print(f"✅ {name}")
        return True
    except AssertionError as e:
        print(f"❌ {name}: {e}")
        return False
    except Exception as e:
        print(f"❌ {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    from services import truth_layer as tl

    results = []

    # ============================================================
    # العقد الأساسي: event_evidence / static_schedule / enum
    # ============================================================

    def test_event_evidence_requires_evidence():
        try:
            tl.build_truth_fact(
                field="unresolved_conflict.count", type_="integer", value=3,
                source="event_evidence", evidence_event_ids=[], computed_by="test",
            )
            raise AssertionError("كان المفروض يرفض -- event_evidence بدون دليل")
        except tl.InvalidTruthFactError:
            pass
    results.append(run_test("event_evidence بدون evidence_event_ids يترفض", test_event_evidence_requires_evidence))

    def test_static_schedule_forbids_evidence():
        try:
            tl.build_truth_fact(
                field="x", type_="integer", value=1,
                source="static_schedule", evidence_event_ids=["e1"], computed_by="test",
            )
            raise AssertionError("كان المفروض يرفض -- static_schedule مينفعش يكون له evidence")
        except tl.InvalidTruthFactError:
            pass
    results.append(run_test("static_schedule مع evidence_event_ids يترفض", test_static_schedule_forbids_evidence))

    def test_enum_requires_allowed_values():
        try:
            tl.build_truth_fact(
                field="x", type_="enum", value="high",
                source="static_schedule", computed_by="test",
            )
            raise AssertionError("كان المفروض يرفض -- enum بدون allowed_values")
        except tl.InvalidTruthFactError:
            pass
    results.append(run_test("enum بدون allowed_values يترفض", test_enum_requires_allowed_values))

    def test_enum_value_must_be_allowed():
        try:
            tl.build_truth_fact(
                field="x", type_="enum", value="extreme",
                source="static_schedule", computed_by="test",
                allowed_values=["none", "elevated", "high"],
            )
            raise AssertionError("كان المفروض يرفض -- 'extreme' مش من ضمن allowed_values")
        except tl.InvalidTruthFactError:
            pass
    results.append(run_test("قيمة enum برّه allowed_values تترفض", test_enum_value_must_be_allowed))

    # ============================================================
    # الأساسي المطلوب: derived facts
    # ============================================================

    def test_derived_requires_derived_from_field():
        try:
            tl.build_truth_fact(
                field="pending_obligation_load.count", type_="integer", value=3,
                source="derived", computed_by="test",
            )
            raise AssertionError("كان المفروض يرفض -- derived بدون derived_from_field")
        except tl.InvalidTruthFactError:
            pass
    results.append(run_test("derived بدون derived_from_field يترفض وقت البناء", test_derived_requires_derived_from_field))

    def test_derived_count_matches_list_length_passes():
        """الاختبار الأول المطلوب: derived fact صحيح لازم ينجح."""
        overdue_items = tl.build_truth_fact(
            field="pending_obligation_load.overdue_items", type_="list",
            value=[{"identity_key": "valu_0"}, {"identity_key": "ca_5"}, {"identity_key": "ca_6"}],
            source="static_schedule", computed_by="test",
        )
        count = tl.build_truth_fact(
            field="pending_obligation_load.count", type_="integer", value=3,
            source="derived", derived_from_field="pending_obligation_load.overdue_items",
            computed_by="test",
        )
        packet = tl.TruthPacket(
            truth_packet_id="test-1", domain="loans", derived_at=tl.now_cairo().isoformat(),
            ttl_seconds=300, facts=[overdue_items, count], integrity={"computation_errors": [], "partial": False},
        )
        errors = tl.validate_truth_packet(packet)
        assert errors == [], f"المفروض مفيش أخطاء خالص، لقيت: {errors}"
    results.append(run_test(
        "derived fact صحيح (count=3 == len(3 عناصر)) -> validate_truth_packet بترجع []",
        test_derived_count_matches_list_length_passes,
    ))

    def test_derived_count_mismatch_is_detected():
        """الاختبار التاني المطلوب: derived fact غلط لازم يتكتشف ويفشل."""
        overdue_items = tl.build_truth_fact(
            field="pending_obligation_load.overdue_items", type_="list",
            value=[{"identity_key": "valu_0"}, {"identity_key": "ca_5"}, {"identity_key": "ca_6"}],
            source="static_schedule", computed_by="test",
        )
        wrong_count = tl.build_truth_fact(
            field="pending_obligation_load.count", type_="integer", value=7,  # غلط عمدًا -- الحقيقي 3
            source="derived", derived_from_field="pending_obligation_load.overdue_items",
            computed_by="test",
        )
        packet = tl.TruthPacket(
            truth_packet_id="test-2", domain="loans", derived_at=tl.now_cairo().isoformat(),
            ttl_seconds=300, facts=[overdue_items, wrong_count], integrity={"computation_errors": [], "partial": False},
        )
        errors = tl.validate_truth_packet(packet)
        assert errors, "المفروض يكتشف التناقض (value=7 لكن len(list)=3) ويرجع خطأ -- رجع [] غلط"
        assert any("pending_obligation_load.count" in e for e in errors), f"الخطأ لازم يشاور على الحقل الغلط، لقيت: {errors}"
    results.append(run_test(
        "derived fact غلط (count=7 لكن len(list)=3) -> validate_truth_packet بتكتشفه وترجع خطأ",
        test_derived_count_mismatch_is_detected,
    ))

    def test_derived_from_field_not_found():
        wrong_ref = tl.build_truth_fact(
            field="pending_obligation_load.count", type_="integer", value=3,
            source="derived", derived_from_field="pending_obligation_load.overdue_items",  # مش موجود في الـ packet
            computed_by="test",
        )
        packet = tl.TruthPacket(
            truth_packet_id="test-3", domain="loans", derived_at=tl.now_cairo().isoformat(),
            ttl_seconds=300, facts=[wrong_ref], integrity={"computation_errors": [], "partial": False},
        )
        errors = tl.validate_truth_packet(packet)
        assert errors, "المفروض يكتشف إن derived_from_field مش موجود في نفس الـ packet"
    results.append(run_test(
        "derived_from_field بيشاور لحقل مش موجود في نفس الـ packet -> بيتكتشف",
        test_derived_from_field_not_found,
    ))

    def test_derived_non_count_no_length_check():
        """derived fact مش integer/list-count (زي enum مشتق) ميتفحصش بفحص len() -- مش من نفس النمط."""
        base = tl.build_truth_fact(
            field="x.raw", type_="integer", value=5, source="static_schedule", computed_by="test",
        )
        derived_enum = tl.build_truth_fact(
            field="x.level", type_="enum", value="high", source="derived",
            derived_from_field="x.raw", computed_by="test", allowed_values=["none", "high"],
        )
        packet = tl.TruthPacket(
            truth_packet_id="test-4", domain="loans", derived_at=tl.now_cairo().isoformat(),
            ttl_seconds=300, facts=[base, derived_enum], integrity={"computation_errors": [], "partial": False},
        )
        errors = tl.validate_truth_packet(packet)
        assert errors == [], f"derived enum من حقل integer مش list -- مفروض يعدي (فحص len() ينطبق بس على list->count)، لقيت: {errors}"
    results.append(run_test(
        "derived fact من نوع enum (مش count-of-list) بيعدي من غير فحص len()",
        test_derived_non_count_no_length_check,
    ))

    # ============================================================
    # TTL / Staleness
    # ============================================================

    def test_is_stale():
        fresh = tl.TruthPacket(
            truth_packet_id="fresh", domain="loans", derived_at=tl.now_cairo().isoformat(),
            ttl_seconds=300, facts=[], integrity={"computation_errors": [], "partial": False},
        )
        assert tl.is_stale(fresh) is False, "packet لسه فريش، مفروض مش stale"

        old_time = (tl.now_cairo() - timedelta(seconds=400)).isoformat()
        stale = tl.TruthPacket(
            truth_packet_id="stale", domain="loans", derived_at=old_time,
            ttl_seconds=300, facts=[], integrity={"computation_errors": [], "partial": False},
        )
        assert tl.is_stale(stale) is True, "packet عمره 400 ثانية وttl=300 -- مفروض يبقى stale"
    results.append(run_test("is_stale() بيفرّق صح بين packet فريش وقديم", test_is_stale))

    # ============================================================
    # النتيجة
    # ============================================================
    print(f"\n{sum(results)}/{len(results)} اختبار عدّى")
    if all(results):
        print("✅✅✅ كل الاختبارات عدّت")
    else:
        print("❌ فيه اختبارات فشلت")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
