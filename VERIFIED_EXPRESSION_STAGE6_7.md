# Verified Expression Layer — Stage 6 + 7 (منفّذ)
تاريخ: 2026-07-24
الحالة: **منفّذ ومتحقق منه فعليًا** ضد Firestore حقيقي، حسب القرارات المقفولة نهائيًا.
المرجع: [VERIFIED_EXPRESSION_STAGE6_7_DRAFT.md](VERIFIED_EXPRESSION_STAGE6_7_DRAFT.md) (كل القرارات وأسبابها)

---

## 1. الملفات

| الملف | الدور |
|---|---|
| [services/expression_vocabulary.py](services/expression_vocabulary.py) | القاموس المقفول (`CLOSED_VOCABULARY`, `VERIFIED_FALSE_VOCABULARY`) -- كود، مش prompt |
| [services/verified_expression.py](services/verified_expression.py) | الـ Gate: `request_verified_expression` (Passive)، `verify_and_finalize` (Verbatim Validator)، `send_active_expression` (Active، صفر LLM) |
| `config.py` | مجموعتين جديدتين: `adam_state_snapshots`, `adam_expressions` |
| `services/claude_service.py` | أداة `request_verified_expression` (مفيش `mode` مكشوفة للموديل)، قيد صريح في الـ system prompt |
| `main.py` | `self_state_active_check_job` (scheduled، كل ساعة) + wiring الـ Verbatim Validator في `handle_message` |
| `handlers/voice_handler.py` | نفس wiring الـ Verbatim Validator |

---

## 2. القرارات المقفولة (منفّذة بالحرف)

- **Active = صفر LLM.** `self_state_active_check_job` (زي `check_loans_job` بالظبط) بينادي `decision_engine` ثم `send_active_expression` مباشرة -- مفيش أي استدعاء لـ Claude في المسار ده خالص.
- **Passive = LLM يختار، مبيؤلفش.** الموديل بينادي `request_verified_expression(dimension)` بس -- **مفيش `mode` في input_schema الأداة أصلًا**، يعني مستحيل الموديل يطلب "active" حتى لو حاول (Information Containment مطبّقة على مستوى الأداة نفسها).
- **الضمان الرسمي = 3 آليات حتمية بس:**
  1. Information Containment -- `verified_expression.py` هو الباب الوحيد؛ مفيش tool بيسرّب أرقام Self-State خام.
  2. Verbatim Match Validator -- `verify_and_finalize()`، متحقق منها فعليًا (قسم 3).
  3. Evidence Trace -- `expression_id → state_id → evidence_event_ids`، متحقق منها فعليًا (قسم 3).
- **الـ Heuristic Scanner: لسه مش متبني** -- زي ما اتفقنا، دفاع إضافي مش جزء من الضمان الرسمي، هيتبني لاحقًا لو ظهر احتياج فعلي (نفس منطق `tracking_stability` في 5.1).

---

## 3. التحقق الفعلي (Verification)

اتعمل بالكامل ضد Firestore الحقيقي (`test_verified_expression.py`)، على نفس الأقساط الآمنة (Credit Agricole 2032):

1. ✅ الأداة مسجّلة صح في `TOOLS`، ومفيش `mode` مكشوفة للموديل.
2. ✅ Passive `verified=true` لمستوى `none` -- نص من القاموس بالحرف.
3. ✅ **Evidence Trace حقيقي**: `expression_id` → `state_id` (StateSnapshot موجودة فعليًا في Firestore) → `evidence_event_ids` بترجع لحدث حقيقي في `adam_events` (اتولّد تعارض حقيقي على القسط الآمن، والدليل اتأكد إنه بيشاور عليه بالظبط).
4. ✅ **Verbatim Match Validator -- الحالة الصح**: رد يحتوي النص بالحرف يعدي من غير تعديل.
5. ✅ **Verbatim Match Validator -- محاولة إعادة صياغة**: رد فيه نفس المعنى بس مش نفس النص بالحرف اترفض، والنص الأصلي اترجع تلقائيًا.
6. ✅ بُعد مش معروف → `verified=false`، نص من قاموس منفصل يصف النقص بس (مفيش تخمين).
7. ✅ **Active -- رفض المستوى الغلط**: طلب إرسال `high` والمستوى الفعلي `elevated` → اترفض (recheck حقيقي، مش اعتماد على قيمة قديمة).
8. ✅ **Active -- إرسال حقيقي**: اتولّدت 3 تعارضات حقيقية (level=`high` فعليًا) → `send_active_expression` نجحت، والنص المُرسل (اتفحص بـ mock لـ `bot.send_message` بدل إرسال حقيقي لتليجرام) طابق القاموس بالحرف بالظبط.
9. 🧹 كل بيانات الاختبار (أحداث + StateSnapshots + Expressions + حالة decision_engine المؤقتة) اتنظفت بالكامل، وكل الأقساط رجعت لحالتها الأصلية.

**ملحوظة منهجية:** التشغيلة الأولى فشلت جزئيًا بسبب bug في التنظيف داخل سكريبت الاختبار نفسه (مش في الكود الأساسي) وسابت أثر حقيقي مؤقت (قسط متعلّم "مدفوع" غلط + حالة `decision_engine` متأثرة ببيانات اختبار). اتكشف واتصلح فورًا، والتشغيلة النهائية عدّت نضيفة بالكامل من غير أي أثر متبقي.

### 3.1 تحقق إضافي بعد سؤال أحمد (مراجعة قبل الاعتماد النهائي، 2026-07-24)

سؤال أحمد كشف فجوة حقيقية في النسخة الأولى من التوثيق: "الفجوة" في قسم 4 (تحت) اتوصفت وقتها كـ "نظرية"، لكن الفحص الفعلي للكود أثبت إنها **مش نظرية خالص**. تفاصيل كاملة في قسم 4 المحدّث.

---

## 4. فجوات معروفة (موثّقة، مش مخفية)

- **[اتقفلت 2026-07-24]** كانت مكتوبة هنا الأول كـ "احتمال ضعيف عمليًا". الفحص الفعلي للكود (رد على سؤال أحمد) أثبت العكس: **9 مسارات callback buttons** (بما فيهم زرار `"loans_month"` -- الأقرب سياقيًا لموضوع الأقساط أصلًا)، `weekly_report_job`، و`morning_brief.py::send_morning_brief` (اللي بيتشغّل يوميًا الساعة 8 صباحًا وبرومبت بتاعه بيقول صراحة "لو فيه قسط قريب اذكره") -- كلهم كانوا بينادوا `ask_claude_agentic` بكامل صلاحية الأدوات (بما فيها `request_verified_expression`) ويبعتوا الرد عبر `bot.send_message` مباشرة **من غير** الـ Verbatim Validator. ده مش احتمال نظري -- morning brief تحديدًا بيتشغّل كل يوم، والبيانات الحقيقية دلوقتي فعلاً `pending_obligation_load = concern`. **اتقفلت الفجوة**: `verified_expression.verify_and_finalize()` اتربطت في كل الـ 11 نقطة إرسال دي (9 callback + weekly_report_job + morning_brief). اتعمل smoke test بـ import فعلي لـ `main.py` كامل بعد التعديل، عدّى نضيف بدون أي خطأ.
- الـ Heuristic Scanner (دفاع إضافي) مش موجود -- يعني لو الموديل "اخترع" جملة عن حالته من غير ما ينادي الأداة أصلًا، مفيش حاجز كود يمسكها (بس القيد في الـ system prompt، طبقة ناعمة).
- تكرار الـ Active job (كل ساعة) اختيار مبدئي -- قابل للتعديل بسهولة.

---

## 5. Definition of Done — مرحلة 6 + 7 (مقترح للاعتماد)

- [x] القاموس المقفول منفّذ للأبعاد التلاتة، بما فيها `verified=false`.
- [x] Evidence Trace كامل وقابل للتحقق (`expression_id → state_id → evidence_event_ids`).
- [x] الضمان الرسمي التلاتة (Information Containment, Verbatim Match Validator, Evidence Trace) منفّذين ومتحقق منهم فعليًا.
- [x] Active = صفر LLM فعليًا (متحقق: mock على `bot.send_message` أثبت المسار بيوصل للإرسال مباشرة من الكود).
- [x] Passive = الموديل مايقدرش يطلب "active" حتى لو حاول (بنية الأداة نفسها بتمنع، مش تعليمة بس).
- [x] تحقق فعلي شامل ضد Firestore حقيقي، بما فيه سيناريو فشل واكتشاف وإصلاح أثناء التنفيذ.
- [x] بيانات الاختبار كلها اتنظفت، كل الأقساط رجعت لأصلها (متحقق فعليًا بفحص مباشر بعد سؤال أحمد، مش بس تصريح).
- [x] الـ Verbatim Validator متربط في **كل** نقاط الإرسال اللي بتستخدم `ask_claude_agentic` (11 نقطة إجمالي) -- مش الرسائل النصية والصوتية بس.
- [ ] **قرار أحمد:** اعتماد المرحلتين كـ "خلصوا". النظام دلوقتي بيقدر فعليًا يعبّر عن حالته الداخلية لأول مرة -- بس بحدود القاموس المقفول والضمانات التلاتة.
