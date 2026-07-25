# Meaning Layer -- Phase 1 (Tests First، منفّذة)
تاريخ: 2026-07-24
الحالة: **منفّذة، Tests First زي Truth Layer بالظبط.** صفر تأثير على الإنتاج -- طبقة معزولة، مش متربطة بأي مسار تشغيل.
المرجع: [TRUTH_LAYER_PHASE1.md](TRUTH_LAYER_PHASE1.md), [TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md](TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md)

---

## المنهجية

1. `test_meaning_layer.py` اتكتب الأول -- 12 اختبار (7 حالات مطلوبة + تفريعات).
2. تأكيد Red: `ImportError` (مفيش `services/meaning_layer.py` أصلًا).
3. `services/meaning_layer.py` اتكتب بعد كده.
4. تأكيد Green: 12/12.
5. Regression check: اختبارات Truth Layer (10/10) لسه عدّية بعد إضافة `truth_packet_confidence` ليها.

---

## الحالات السبعة المطلوبة -- كل واحدة ومطابقها

| # | المطلوب | الاختبار | النتيجة |
|---|---|---|---|
| 1 | فلترة facts حسب target_dimension | `test_filters_facts_by_dimension` | ✅ |
| 2 | fired_inferences من الـ domain الصحيح بس | `test_filters_inferences_by_domain` + `test_filters_inferences_by_dimension_too` (تفريع إضافي: نفس الـ domain لكن dimension مختلف بيترفلتر برضه) | ✅✅ |
| 3 | primary_focus/allowed_topics حتمي | `test_primary_focus_and_allowed_topics_single_dimension` + `test_primary_secondary_focus_multi_dimension` | ✅✅ |
| 4 | confidence بيترحّل من غير تغيير | `test_confidence_full_when_not_partial` + `test_confidence_degraded_when_partial` | ✅✅ |
| 5 | ترتيب حسب priority_order | `test_priority_order_sorted_by_score` | ✅ |
| 6 | رفض target_dimension غير موجود/غير مسموح | `test_rejects_unknown_dimension` (مش معروف أصلًا) + `test_rejects_dimension_not_in_packet` (معروف لكن مش في الـ packet ده) | ✅✅ |
| 7 | صفر LLM / صفر احتمالية | `test_no_llm_calls_in_module_source` (فحص بنيوي على نص الملف نفسه) + `test_pure_function_same_input_same_output` (حتمية فعلية: نفس المدخل = نفس المخرج) | ✅✅ |

---

## قرارات تصميم اتخدت أثناء التنفيذ (مش في v2 بالتفصيل ده)

- **`DIMENSION_PRIORITY` كـ Priority Scores** (`{"unresolved_conflict": 30, "pending_obligation_load": 20, "tracking_stability": 10}`) -- زي ما فضّلت بالظبط ("Priority Scores بدل ترتيب ثابت فقط"). إضافة بُعد جديد مستقبلًا = رقم واحد يتضاف هنا.
- **فلترة الاستنتاجات بقت مزدوجة**: `domain` **و** `dimension` سوا، مش `domain` بس. لو نفس الـ domain (loans) فيه قاعدة خاصة ببُعد تاني (pending_obligation_load) واتطلب `unresolved_conflict` بس، القاعدة دي بتترفلتر برضه -- مش بس حماية من تسرّب بين domains، كمان بين dimensions في نفس الـ domain.
- **`target_dimensions` بتقبل واحد أو أكتر** (مش بس واحد زي الرسم الأولي في v2) -- عشان `primary_focus`/`secondary_focus`/`priority_order` يكون لها معنى فعلي لما أكتر من بُعد يتطلب مرة واحدة.

---

## الحالة والخطوة الجاية

- [x] Tests First كامل، بما فيهم الحالات السبعة المطلوبة كلها.
- [x] فحص بنيوي حقيقي (مش افتراض) إن الملف خالي من أي استدعاء LLM.
- [x] Regression check على Truth Layer -- لسه سليمة.
- [ ] لسه الجزء المتبقي من Phase 1: **Companionship Layer** (LLM -- الاستدعاء الوحيد في الـ pipeline) + **Renderer** (Slot-Based، حتمي) + **Claim Validator**.
- [ ] مفيش ربط بأي مسار تشغيل حالي لسه.
