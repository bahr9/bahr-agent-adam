# -*- coding: utf-8 -*-
"""
Tests First -- Meaning Layer (Architecture v2). اتكتبت قبل أي سطر في
services/meaning_layer.py. الأساس الحاكم لكل التصميم: Meaning Layer
Backend بحت، بدون LLM خالص (v2، قسم 1) -- فلترة وترتيب على بيانات
Truth Layer الموجودة فعليًا، مفيش "فهم" أو استنتاج جديد.

7 حالات مطلوبة تحديدًا:
  1. فلترة الـ facts حسب target_dimension.
  2. اختيار fired_inferences المرتبطة بالـ domain الصحيح بس.
  3. بناء primary_focus و allowed_topics بشكل حتمي.
  4. تمرير confidence من Truth Packet من غير تغيير.
  5. ترتيب النتائج حسب priority_order.
  6. رفض target_dimension غير موجود أو غير مسموح.
  7. التأكد إن الطبقة مفيهاش أي استدعاء LLM أو اعتماد على output احتمالي.

لا يحتاج Firestore -- بيانات TruthPacket مصطنعة بالكامل (Unit Tests).
"""


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


def _make_packet(tl, extra_facts=None, partial=False):
    """Truth Packet مصطنع فيه الثلاث أبعاد المعروفة -- زي الحقيقي بالظبط."""
    facts = [
        tl.build_truth_fact(
            field="unresolved_conflict.count", type_="integer", value=3,
            source="event_evidence", evidence_event_ids=["e1", "e2", "e3"], computed_by="test",
        ),
        tl.build_truth_fact(
            field="unresolved_conflict.level", type_="enum", value="high",
            source="event_evidence", evidence_event_ids=["e1", "e2", "e3"], computed_by="test",
            allowed_values=["none", "elevated", "high"],
        ),
        tl.build_truth_fact(
            field="pending_obligation_load.count", type_="integer", value=7,
            source="static_schedule", computed_by="test",
        ),
        tl.build_truth_fact(
            field="pending_obligation_load.level", type_="enum", value="concern",
            source="derived", derived_from_field="pending_obligation_load.count", computed_by="test",
            allowed_values=["none", "light", "concern"],
        ),
        tl.build_truth_fact(
            field="tracking_stability.count", type_="integer", value=0,
            source="static_schedule", computed_by="test",
        ),
        tl.build_truth_fact(
            field="tracking_stability.level", type_="enum", value="none",
            source="static_schedule", computed_by="test",
            allowed_values=["none", "frequent_corrections"],
        ),
    ]
    if extra_facts:
        facts.extend(extra_facts)
    return tl.TruthPacket(
        truth_packet_id="test-packet", domain="loans", derived_at=tl_now(tl),
        ttl_seconds=300, facts=facts,
        integrity={"computation_errors": [], "partial": partial},
    )


def tl_now(tl):
    from utils.time_utils import now_cairo
    return now_cairo().isoformat()


def main():
    from services import truth_layer as tl
    from services import meaning_layer as ml

    results = []

    # ============================================================
    # 1. فلترة الـ facts حسب target_dimension
    # ============================================================
    def test_filters_facts_by_dimension():
        packet = _make_packet(tl)
        fired_rules = []
        meaning = ml.compute_meaning_packet(packet, "unresolved_conflict", fired_rules)
        assert set(meaning["referenced_facts"].keys()) == {"unresolved_conflict.count", "unresolved_conflict.level"}, \
            f"المفروض بس حقول unresolved_conflict، لقيت: {meaning['referenced_facts'].keys()}"
        assert "pending_obligation_load.count" not in meaning["referenced_facts"]
    results.append(run_test("referenced_facts بتتفلتر حسب target_dimension بس", test_filters_facts_by_dimension))

    # ============================================================
    # 2. fired_inferences من الـ domain الصحيح بس
    # ============================================================
    def test_filters_inferences_by_domain():
        packet = _make_packet(tl)
        fired_rules = [
            {"rule_id": "unresolved_conflict_high", "domain": "loans", "dimension": "unresolved_conflict", "text": "الوضع محتاج مراجعة عاجلة"},
            {"rule_id": "foreign_rule", "domain": "projects", "dimension": "unresolved_conflict", "text": "حاجة من مجال تاني"},
        ]
        meaning = ml.compute_meaning_packet(packet, "unresolved_conflict", fired_rules)
        rule_ids = [r["rule_id"] for r in meaning["fired_inferences"]]
        assert rule_ids == ["unresolved_conflict_high"], f"المفروض بس قاعدة الـ domain الصحيح (loans)، لقيت: {rule_ids}"
    results.append(run_test("fired_inferences بتتفلتر بالـ domain الصحيح بس (مش أي domain)", test_filters_inferences_by_domain))

    def test_filters_inferences_by_dimension_too():
        packet = _make_packet(tl)
        fired_rules = [
            {"rule_id": "unresolved_conflict_high", "domain": "loans", "dimension": "unresolved_conflict", "text": "..."},
            {"rule_id": "obligation_concern", "domain": "loans", "dimension": "pending_obligation_load", "text": "..."},
        ]
        meaning = ml.compute_meaning_packet(packet, "unresolved_conflict", fired_rules)
        rule_ids = [r["rule_id"] for r in meaning["fired_inferences"]]
        assert rule_ids == ["unresolved_conflict_high"], \
            f"نفس الـ domain لكن dimension مختلف مفروض يترفلتر برضه، لقيت: {rule_ids}"
    results.append(run_test("fired_inferences من نفس الـ domain لكن dimension مختلف بتترفلتر برضه", test_filters_inferences_by_dimension_too))

    # ============================================================
    # 3. primary_focus و allowed_topics حتمي
    # ============================================================
    def test_primary_focus_and_allowed_topics_single_dimension():
        packet = _make_packet(tl)
        meaning = ml.compute_meaning_packet(packet, "unresolved_conflict", [])
        assert meaning["primary_focus"] == "unresolved_conflict"
        assert meaning["allowed_topics"] == ["unresolved_conflict"]
    results.append(run_test("primary_focus و allowed_topics صح لبُعد واحد", test_primary_focus_and_allowed_topics_single_dimension))

    def test_primary_secondary_focus_multi_dimension():
        packet = _make_packet(tl)
        # pending_obligation_load أولوية أقل من unresolved_conflict -- المفروض يبقى secondary
        meaning = ml.compute_meaning_packet(packet, ["pending_obligation_load", "unresolved_conflict"], [])
        assert meaning["primary_focus"] == "unresolved_conflict", \
            f"unresolved_conflict أولوية أعلى، المفروض يبقى primary_focus بغض النظر عن ترتيب الطلب، لقيت: {meaning['primary_focus']}"
        assert meaning["secondary_focus"] == ["pending_obligation_load"]
    results.append(run_test("primary_focus بيتحدد بالأولوية مش بترتيب الطلب", test_primary_secondary_focus_multi_dimension))

    # ============================================================
    # 4. confidence من Truth Packet من غير تغيير
    # ============================================================
    def test_confidence_full_when_not_partial():
        packet = _make_packet(tl, partial=False)
        meaning = ml.compute_meaning_packet(packet, "unresolved_conflict", [])
        assert meaning["confidence"] == "full"
    results.append(run_test("confidence='full' لما integrity.partial=False", test_confidence_full_when_not_partial))

    def test_confidence_degraded_when_partial():
        packet = _make_packet(tl, partial=True)
        meaning = ml.compute_meaning_packet(packet, "unresolved_conflict", [])
        assert meaning["confidence"] == "degraded"
    results.append(run_test("confidence='degraded' لما integrity.partial=True (بدون حساب إضافي، بترث القيمة زي ما هي)", test_confidence_degraded_when_partial))

    # ============================================================
    # 5. ترتيب النتائج حسب priority_order
    # ============================================================
    def test_priority_order_sorted_by_score():
        packet = _make_packet(tl)
        meaning = ml.compute_meaning_packet(packet, ["tracking_stability", "pending_obligation_load", "unresolved_conflict"], [])
        assert meaning["priority_order"] == ["unresolved_conflict", "pending_obligation_load", "tracking_stability"], \
            f"المفروض ترتيب حسب DIMENSION_PRIORITY الثابت بغض النظر عن ترتيب الطلب، لقيت: {meaning['priority_order']}"
    results.append(run_test("priority_order بترتب الأبعاد حسب Priority Score ثابت، مش ترتيب الطلب", test_priority_order_sorted_by_score))

    # ============================================================
    # 6. رفض target_dimension غير موجود أو غير مسموح
    # ============================================================
    def test_rejects_unknown_dimension():
        packet = _make_packet(tl)
        try:
            ml.compute_meaning_packet(packet, "some_random_dimension", [])
            raise AssertionError("كان المفروض يرفض -- بُعد مش معروف أصلًا")
        except ml.InvalidMeaningRequestError:
            pass
    results.append(run_test("target_dimension مش معروف (مش في DIMENSION_PRIORITY) يترفض", test_rejects_unknown_dimension))

    def test_rejects_dimension_not_in_packet():
        # packet مالوش غير unresolved_conflict -- الأبعاد التانية مش موجودة فيه
        facts = [
            tl.build_truth_fact(
                field="unresolved_conflict.count", type_="integer", value=0,
                source="static_schedule", computed_by="test",
            ),
        ]
        packet = tl.TruthPacket(
            truth_packet_id="partial-packet", domain="loans", derived_at=tl_now(tl),
            ttl_seconds=300, facts=facts, integrity={"computation_errors": [], "partial": False},
        )
        try:
            ml.compute_meaning_packet(packet, "tracking_stability", [])
            raise AssertionError("كان المفروض يرفض -- tracking_stability مش موجود في الـ packet ده أصلًا")
        except ml.InvalidMeaningRequestError:
            pass
    results.append(run_test("target_dimension معروف لكن مش موجود في الـ packet المُعطى يترفض", test_rejects_dimension_not_in_packet))

    # ============================================================
    # 7. مفيش LLM ولا output احتمالي -- فحص بنيوي على مصدر الملف نفسه
    # ============================================================
    def test_no_llm_calls_in_module_source():
        import services.meaning_layer as ml_module
        source = open(ml_module.__file__, encoding="utf-8").read()
        forbidden_tokens = [
            "anthropic", "claude_client", "ask_claude", "messages.create",
            "claude_service", ".create(", "openai",
        ]
        found = [tok for tok in forbidden_tokens if tok in source]
        assert not found, f"لقيت إشارات لاستدعاء LLM في meaning_layer.py: {found} -- المفروض الملف backend بحت"
    results.append(run_test("meaning_layer.py مفيهوش أي استدعاء LLM (فحص بنيوي على المصدر)", test_no_llm_calls_in_module_source))

    def test_pure_function_same_input_same_output():
        """اختبار حتمية إضافي: نفس المدخلات لازم تدي نفس المخرجات بالظبط، كل مرة."""
        packet = _make_packet(tl)
        fired_rules = [{"rule_id": "unresolved_conflict_high", "domain": "loans", "dimension": "unresolved_conflict", "text": "..."}]
        r1 = ml.compute_meaning_packet(packet, "unresolved_conflict", fired_rules)
        r2 = ml.compute_meaning_packet(packet, "unresolved_conflict", fired_rules)
        assert r1 == r2, "نفس المدخلات المفروض تدي نفس المخرجات بالظبط (دالة حتمية، مفيش عشوائية أو LLM)"
    results.append(run_test("نفس المدخلات بتدي نفس المخرجات بالظبط (حتمية، صفر عشوائية)", test_pure_function_same_input_same_output))

    # ============================================================
    print(f"\n{sum(results)}/{len(results)} اختبار عدّى")
    if all(results):
        print("✅✅✅ كل الاختبارات عدّت")
    else:
        print("❌ فيه اختبارات فشلت")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
