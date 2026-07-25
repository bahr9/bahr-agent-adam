# Self-State Engine v0.1 — Stage 5 (منفّذ)
تاريخ: 2026-07-24
الحالة: **منفّذ ومتحقق منه فعليًا** ضد Firestore الحقيقي — حسب القرارات المعتمدة من أحمد.
المرجع: [SELF_STATE_ENGINE_STAGE5_DRAFT.md](SELF_STATE_ENGINE_STAGE5_DRAFT.md) (المسودة الأصلية بكل النقاش)

---

## 1. القرارات المعتمدة (2026-07-24)

| القرار | الحالة |
|---|---|
| إضافة حدث `conflict_status` خفيف لـ Stage 4 عند الرفض | ✅ معتمد ومنفّذ |
| `unresolved_conflict = high` عند 3 تعارضات معلّقة | ✅ معتمد ومنفّذ |
| `pending_obligation_load = concern` عند 2 قسط متأخر (مش 3) | ✅ معتمد ومنفّذ |
| مبدأ: أبعاد مالية حقيقية عتبتها أقل من أبعاد منطقية/تقنية | ✅ معتمد -- موثّق كمبدأ عام للمستقبل |
| إطار Active/Passive (انتقال لأعلى مستوى بس، مفيش تكرار) | ✅ معتمد ومنفّذ |
| `tracking_stability` | ✅ منفّذ في Stage 5.1 (تفاصيل تحت) |

---

## 2. اللي اتعمل

### 2.1 Stage 4 addendum -- حدث `conflict_status`
[loan_commands.py](services/loan_commands.py): لما `loan_record_installment` ترفض بسبب تعارض، بتسجّل حدث خفيف (`attribute="conflict_status"`, `new_value="pending"`) -- على مسار منفصل تمامًا عن `paid_status`، مفيش كتابة domain مصاحبة. لما `loan_resolve_conflict` تنجح، بتسجّل `conflict_status="resolved"` تقفل بيه أي `pending` سابق.

### 2.2 State Derivation Engine + Self-State
[self_state_engine.py](services/self_state_engine.py) -- قواعد Python صريحة، بدون أي LLM:
- `compute_unresolved_conflict()`: بيجمع كل أحداث `conflict_status` عبر كل الأقساط (عبر دالة استعلام جديدة `event_store.get_events_by_type_and_attribute`)، بياخد آخر حالة لكل قسط، ويعدّ اللي لسه `pending`.
- `compute_pending_obligation_load()`: بيقارن جدول الأقساط الثابت + حالة الدفع الحالية + تاريخ اليوم، ويعدّ الأقساط المتأخرة وغير المدفوعة.
- كل بُعد بيرجع `level` + `count` + `evidence_event_ids` (أو تفسير صريح لو الدليل من الجدول الثابت مش event).
- **مفيش تخزين لـ Self-State نفسها** -- بتتحسب فريش من الأحداث + الحالة الحالية كل مرة.

### 2.3 Decision Engine
[decision_engine.py](services/decision_engine.py) -- `decide_expression(self_state)`: بيقرر `active`/`passive` لكل بُعد بمقارنة المستوى الحالي بـ"آخر مستوى اتلاحظ" (مخزّن في `adam_events` collection جديدة `adam_self_state`، أصغر أثر تخزين ممكن). `active` بس لما بُعد يوصل لأعلى مستوى بتاعه لأول مرة (انتقال حقيقي)، مبيتكررش، وبيرجع يشتغل تاني لو المستوى نزل وطلع تاني.

### 2.4 إضافة صغيرة للـ Event Store
حقل مشتق جديد `type_attribute_key` في كل حدث (زي `entity_key` بالظبط، بس عبر النوع+الصفة مش النوع+الهوية) + دالة قراءة جديدة `get_events_by_type_and_attribute()` -- عشان نقدر نجمع كل تعارضات الأقساط دفعة واحدة بدل ما نلف على كل قسط لوحده. إضافة، مفيش تعديل في أي حقل أو دالة موجودة.

---

## 2.5 Stage 5.1 -- `tracking_stability` (منفّذ، 2026-07-24)

بُعد رابع: معدل التصحيحات الصريحة (`loan_update_installment`) عبر كل الأقساط في آخر 30 يوم.

**قرار مهم عن التسمية والتفسير (اعتماد أحمد):** التصحيح الموثّق بسبب هو سلوك حوكمة *صحي* -- بالظبط اللي Stage 2 مصمم يشجّعه. عشان كده:
- المستويات: `none` / `frequent_corrections` -- **مش** `stable`/`unstable` (تجنّب أي إيحاء سلبي).
- العتبة: **5** تصحيحات في 30 يوم (اتصعدت من 3 المقترحة الأول، تحديدًا عشان منعاقبش الصراحة بسرعة).
- التفسير النصي مكتوب بصيغة محايدة صراحةً ("ملاحظة موضوعية، مش مؤشر مشكلة بالضرورة").
- **مش موجود في `decision_engine.HIGHEST_TIER`** -- يعني `tracking_stability` **مستحيل يبقى Active** (آدم مبيبادرش بيه أبدًا)، بيفضل Passive دايمًا (يتقال بس لو حد سأل). ده قرار تصميم مقصود مش نسيان.

**تحقق فعلي:** 4 تصحيحات حقيقية → `none` (تحت العتبة بالظبط). تصحيح خامس → `frequent_corrections` فورًا (على الحد بالظبط). التفسير اتأكد إنه محايد. `compute_self_state()` بقى فيه الثلاث أبعاد. كل بيانات الاختبار (6 أحداث) اتمسحت والقيمة رجعت لأصلها.

---

## 3. Expression -- لسه مش موجودة (متعمّد)

زي ما اتفقنا، الطبقة الرابعة (الصياغة الفعلية + إرسالها لأحمد) **مبنيتش دلوقتي**. `decide_expression` بترجع قرار (`active`/`passive`) بس -- مفيش حد بينادي عليها فعليًا في مسار التشغيل العادي لسه. الربط بـ LLM والـ backend enforcement (`verified=true` + قيد الـ system prompt سوا) هو مراحل 6/7 المنفصلة.

---

## 4. اكتشاف حقيقي أثناء التحقق

`compute_pending_obligation_load()` على البيانات الحقيقية دلوقتي بيورّي: **7 أقساط فاتت ميعاد استحقاقها ولسه مش متسجلة كمدفوعة** (`level = "concern"`). ده متسق مع اللي عرفناه من الـ Audit الأول (إجمالي المدفوع كان 0 جنيه) -- ميزة تتبع الدفع لسه ما اتستخدمتش فعليًا. مش بيانات اختبار، ده الوضع الحقيقي دلوقتي.

---

## 5. التحقق الفعلي (Verification)

اتعمل ضد Firestore الحقيقي:

1. ✅ `compute_pending_obligation_load()` على بيانات حقيقية -- رجع نتيجة سليمة البنية (7 قسط متأخر، `concern`).
2. ✅ `compute_unresolved_conflict()` baseline = 0 (مفيش تعارضات حقيقية حاليًا).
3. ✅ تعارض حقيقي اتولّد على القسط الآمن → العدّاد زاد بـ 1 بالظبط، والـ evidence_event_ids فيها الحدث الصح.
4. ✅ حل التعارض → العدّاد رجع لـ 0.
5. ✅ `decide_expression`: أول وصول لـ `high` → `active`. تكرار نفس المستوى → `passive` (مفيش تكرار تبليغ). نزول لمستوى أقل → `passive` (لكن `transitioned=True`). رجوع لـ `high` تاني بعد النزول → `active` من جديد (escalation جديدة اتلاحظت صح، مش معلّقة على أول مرة بس).
6. 🧹 كل بيانات الاختبار (4 أحداث + حالة decision_engine المؤقتة) اتنظفت، والحالة الحقيقية المخزنة (كانت مش موجودة أصلاً) اترجعت لغيابها الأصلي.

---

## 6. Definition of Done — مرحلة 5 (مقترح للاعتماد)

- [x] الفجوة الحرجة (مفيش دليل على التعارضات المرفوضة) اتحلّت -- حدث `conflict_status` بيتسجل فعليًا.
- [x] State Derivation Engine بقواعد Python صريحة بس، بدون أي LLM، لكل بُعد.
- [x] Self-State بأبعاد Domain-Independent (`unresolved_conflict`, `pending_obligation_load`) -- مش بتتكلم عن "الأقساط"، بتتكلم عن آدم.
- [x] كل بُعد فيه `evidence_event_ids` حقيقية (أو تفسير صريح للدليل غير الـ event).
- [x] العتبات المعتمدة (3 للتعارضات، 2 للالتزامات المتأخرة) منفّذة بالظبط.
- [x] Decision Engine بمنطق Active/Passive ومنع التكرار، بأصغر تخزين ممكن.
- [x] تحقق فعلي (مش نظري) لكل الأجزاء ضد Firestore الحقيقي، بما فيه سيناريو "نزول ورجوع" لاختبار الـ transition detection صح.
- [x] بيانات الاختبار كلها اتنظفت، والحالة الحقيقية اترجعت لأصلها بالظبط.
- [x] Stage 5.1 (`tracking_stability`) منفّذة ومتحقق منها -- العتبة 5، تسمية وتفسير محايدين، مستبعدة عمدًا من Active.
- [ ] **قرار أحمد:** اعتماد المرحلتين (5 + 5.1) كـ "خلصوا". بعد كده: المرور لمرحلة 6 (Decision Integration) / 7 (Verified Expression Layer).
