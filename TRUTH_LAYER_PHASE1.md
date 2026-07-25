# Truth Layer -- Phase 1 (Tests First، منفّذة)
تاريخ: 2026-07-24
الحالة: **منفّذة، Tests First زي ما اتطلب بالحرف.** صفر تأثير على الإنتاج (طبقة جديدة معزولة، مش متربطة بأي مسار تشغيل حالي).
المرجع: [TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md](TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md)

---

## المنهجية -- بالترتيب الفعلي

1. **`test_truth_layer.py` اتكتب الأول** -- 10 اختبارات، قبل ما `services/truth_layer.py` يكون موجود خالص.
2. **تأكيد Red**: تشغيل الاختبارات وقتها فشل بـ `ImportError` (مفيش الملف أصلًا) -- الحالة الحمراء موثّقة فعليًا، مش افتراض.
3. **`services/truth_layer.py` اتكتب بعد كده**، عشان يُرضي العقد اللي الاختبارات فرضته -- مش العكس.
4. **تأكيد Green**: 10/10 اختبار عدّى.
5. **تحقق إضافي ضد بيانات حقيقية** (`build_truth_packet_for_loans`): نفس منطق التحقق (`validate_truth_packet`) اتجرّب على Truth Packet حقيقي من `self_state_engine.compute_self_state()` الفعلي -- `pending_obligation_load.count=7` طابق `len(overdue_items)=7` صح، و `validate_truth_packet` رجّع `[]`.

---

## الاختبارين الأساسيين المطلوبين تحديدًا

| # | الاختبار | النتيجة |
|---|---|---|
| 1 | `derived fact` صحيح (`count=3 == len(3 عناصر)`) | ✅ `validate_truth_packet` بترجع `[]` |
| 2 | `derived fact` غلط (`count=7` لكن `len(list)=3`) | ✅ `validate_truth_packet` بتكتشف التناقض وترجع خطأ واضح يشاور على الحقل الغلط |

باقي الـ 8 اختبارات بتثبت العقد الأساسي الكامل (event_evidence/static_schedule/derived/enum + TTL) -- جزء من نفس الـ Contract، مش إضافة منفصلة.

---

## حدود التحقق -- زي ما اتفقنا بالضبط

`validate_truth_packet` بتتأكد من:
- **صحة الربط** دايمًا (derived_from_field موجود فعليًا في نفس الـ packet).
- **تطابق العدد** لحالة خاصة شائعة بس: `integer` مشتق من `list` (`count == len(list)`) -- فحص حتمي رخيص لنمط محدد ومعروف، **مش تحقق عام لأي صيغة حسابية**.

أي علاقة حسابية أعقد (زي `pending_obligation_load.level` المشتقة من `count` عبر threshold) **مش بتتفحص حسابيًا هنا** -- دي مسؤولية `self_state_engine.py` نفسه واختباراته (Stage 5، موجودة ومتحقق منها فعليًا من قبل). ده الحد اللي اتفقنا عليه صراحة، موثّق هنا تاني عشان يفضل واضح.

---

## `build_truth_packet_for_loans()` -- الربط بالبنية الموجودة

مفيش إعادة حساب -- بيغلّف `self_state_engine.compute_self_state()` (Stage 5، معتمد ومتحقق منه فعليًا) في `TruthPacket` رسمي. مصادر كل حقل:
- `unresolved_conflict.*`: `event_evidence` لو فيه تعارضات فعلية، `static_schedule` لو صفر (مفيش أحداث تتشاور عليها).
- `pending_obligation_load.overdue_items`: `static_schedule` (جدول الأقساط الثابت + غياب حدث دفع).
- `pending_obligation_load.count`: `derived` من `overdue_items` -- **نفس الحالة اللي كانت فيها الفجوة الأصلية في مثال v1، اتصلحت فعليًا هنا**.
- `pending_obligation_load.level`: `derived` من `count` (threshold، مش count-of-list -- مفيش فحص len() عليها، وده صح لأنها مش من نفس النمط).
- `tracking_stability.*`: نفس نمط `unresolved_conflict`.

اتجرّب فعليًا ضد Firestore الحقيقي (read-only، مفيش كتابة): 7 أقساط متأخرة حقيقية، `validate_truth_packet` رجّعت `[]`.

---

## الحالة والخطوة الجاية

- [x] Tests First -- الاختبارات اتكتبت وفشلت (Red) قبل أي كود.
- [x] `services/truth_layer.py` بيرضي كل الاختبارات (Green).
- [x] تحقق إضافي ضد بيانات حقيقية حقيقية (مش synthetic بس).
- [x] `build_truth_packet_for_loans()` جاهزة كنقطة دخول حقيقية لباقي الـ pipeline.
- [ ] **مرحلة 1 لسه ناقصها**: `Meaning Layer` (backend، بدون LLM -- قسم 1 من v2) لسه مش متبنية. دي الخطوة التالية المنطقية.
- [ ] مفيش أي ربط بمسار تشغيل حالي لسه -- الطبقة دي معزولة تمامًا، صفر تأثير على الإنتاج، زي ما اتفقنا في خطة الـ Migration.
