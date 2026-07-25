# Architecture Recovery — Inventory كامل لملفات Truth/Meaning/Companionship
تاريخ: 2026-07-24
الحالة: **جرد وفحص فقط. صفر دمج، صفر تعديل على كود الإنتاج.**
المرجع: [CHECKPOINT_2026-07-24.md](CHECKPOINT_2026-07-24.md)

**منهجية الفحص:** كل سطر هنا مبني على تشغيل فعلي (`python test_*.py`) أو قراءة كود مباشرة أو `grep` على الاستيرادات -- مش على قراءة التوثيق وتصديقه. حيث وجدت تناقض بين ما يدّعيه التوثيق وما شغّلته فعليًا، الأولوية للتشغيل الفعلي.

---

## 1. الجرد الكامل

### أ) مستندات (5)

| الملف | الوظيفة | الحالة الموثّقة (ادّعاء) | الحالة الفعلية (تحقّق مني) |
|---|---|---|---|
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md` | التصميم الأصلي الكامل (v1) -- Schema، Pipeline، خطة migration بـ 7 مراحل (Shadow Mode) | "تصميم تنفيذي كامل، لسه مش متبني" | مستند تصميم فقط، لا كود منفّذ منه مباشرة (بعض أفكاره اتنفذت بتعديل في v2) |
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` | مراجعة معمارية تصحّح 3 عيوب في v1 (Meaning تبقى بلا LLM، Slot-Based Rendering، إصلاح بند 10.1) + قرارات إضافية (Confidence, Decision Trace, Constitution) | "تعديل جوهري... لسه مفيش كود" | مستند تصميم، **لكن أجزاء منه (Truth/Meaning/Renderer) اتنفذت فعليًا بعده مباشرة** |
| `TRUTH_LAYER_PHASE1.md` | توثيق تنفيذ Truth Layer (Tests First) | "منفّذة، Tests First بالحرف" | ✅ **مؤكد بالتشغيل الفعلي** -- 10/10 اختبار عدّى |
| `MEANING_LAYER_PHASE1.md` | توثيق تنفيذ Meaning Layer (Tests First) | "منفّذة، Tests First زي Truth Layer" | ✅ **مؤكد بالتشغيل الفعلي** -- 12/12 اختبار عدّى |
| `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` | إعادة نظر مقترحة في قرار "قاموس مقفول" (مرحلة 6/7) -- 4 مستويات حرية، توصية بمستوى 1 | "مسودة تصميم فقط" | ✅ متطابق -- لا كود، لا تنفيذ، مجرد اقتراح مطروح للنقاش |

### ب) كود (3 موجود + 4 مفقود مذكورين في الخطة)

| الملف | الوظيفة | الحالة الفعلية (تحقّق مني) |
|---|---|---|
| `services/truth_layer.py` | `TruthFact`/`TruthPacket` + `build_truth_fact` (يرفض بناء غير متسق) + `validate_truth_packet` + `build_truth_packet_for_loans()` (يغلّف `self_state_engine.compute_self_state()` الموجود -- **قراءة فقط، صفر كتابة Firestore**) | ✅ **10/10 اختبار عدّى فعليًا** (شغّلته بنفسي) |
| `services/meaning_layer.py` | `compute_meaning_packet()` -- فلترة/ترتيب حتمي بحت، صفر LLM (مؤكد ببحث نصي في الاختبار نفسه عن استدعاءات LLM) | ✅ **12/12 اختبار عدّى فعليًا** |
| `services/renderer.py` | `render()` -- يملأ Slots (`{field}`, `{inference:rule_id}`) بقيم حقيقية من Meaning Packet، يرفض أي slot غير معروف فورًا | ✅ **10/10 اختبار عدّى فعليًا** (فشل أول مرة بسبب مشكلة ترميز Windows console، مش خطأ حقيقي -- أعدت التشغيل بـ UTF-8 وعدّى كامل) |
| `services/claim_validator.py` | **مفقود -- غير موجود على القرص إطلاقًا** | ❌ **غير منفّذ**. `test_claim_validator.py` (11 اختبار مكتوبة) بيفشل فورًا بـ `ImportError` -- هذه هي حالة "Red" في منهجية Tests First، **متوقفة قبل خطوة التنفيذ (Green)** |
| `services/inference_rules.py` | (مخطط) `INFERENCE_RULES` + `evaluate_fired_rules()` | ❌ غير موجود على القرص |
| `services/companionship_layer.py` | (مخطط) استدعاء LLM الوحيد المتبقي في الـ pipeline | ❌ غير موجود على القرص |
| `services/decision_trace.py` | (مخطط) تسجيل قرارات Active/Passive بشكل دائم | ❌ غير موجود على القرص |
| `CONSTITUTION.md` | (مخطط) ملف مرجعي يجمع كل المبادئ السبعة وآليات فرضها | ❌ غير موجود على القرص |

### ج) اختبارات (4)

| الملف | عدد الاختبارات | النتيجة الفعلية (تشغيل مباشر الآن) |
|---|---|---|
| `test_truth_layer.py` | 10 | ✅ 10/10 |
| `test_meaning_layer.py` | 12 | ✅ 12/12 |
| `test_renderer.py` | 10 | ✅ 10/10 |
| `test_claim_validator.py` | 11 | ❌ **ImportError فوري** -- الوحدة المستهدفة غير موجودة |

---

## 2. الاعتماديات (مؤكدة بـ `grep`، مش افتراض)

- `truth_layer.py` → يستدعي `self_state_engine.compute_self_state()` (Stage 5، **قراءة فقط**، صفر كتابة). لا اعتماد على `event_store`/`loan_commands`/`verified_expression`/`decision_engine` مباشرة.
- `meaning_layer.py` → يستدعي `truth_layer.truth_packet_confidence()` بس. لا اعتماد على `inference_rules` (بيستقبل `fired_rules` كـ parameter عادي، مش import مباشر) -- يعني قابل للاختبار بمعزل حتى قبل ما `inference_rules.py` يتبنى.
- `renderer.py` → لا اعتماديات داخلية إطلاقًا (regex + stdlib بس).
- **لا ملف من مراحل 1-7 (`event_store`, `loan_commands`, `self_state_engine`, `decision_engine`, `verified_expression`, `claude_service`, `main.py`) يستورد أو يذكر أي من `truth_layer`/`meaning_layer`/`renderer`** -- مؤكد بـ `grep` مباشر، صفر نتائج.
- **لا كتابة Firestore** في أي من الملفات الثلاثة المنفّذة -- قراءة فقط.
- Collections مخطط لها (`adam_truth_packets`, `adam_meaning_packets`) **غير موجودة في `config.py` فعليًا** (مؤكد بـ `git diff` -- لم تُضَف).

---

## 3. التعارضات المحتملة مع معمارية مراحل 1-7

### لا يوجد تعارض فعلي حاليًا (الحالة الآن)
لأن الطبقة الجديدة **غير مربوطة بأي مسار تشغيل**، ولا تكتب أي بيانات، فلا يوجد أي تعارض حي في هذه اللحظة. هذا مؤكد وليس افتراضًا (قسم 2 فوق).

### تعارضات/مخاطر **مستقبلية** إذا تم الدمج بدون مراجعة (مذكورة صراحة في خطة V1/V2 نفسها، وأعيد التأكيد عليها هنا):

1. **تعديل مقترح على `self_state_engine.py`** (إضافة `computation_ok` لكل دالة `compute_*`، تغيير قيمة الإرجاع من قيمة مفردة لـ `(value, computation_ok)`) -- هذا **تعديل جوهري على عقد دالة معتمدة ومتحقق منها بالكامل في مرحلة 5**. أي دمج مستقبلي لازم يعيد اختبار كل الاستدعاءات الحالية لـ `compute_self_state()` (في `loan_commands.py`, `verified_expression.py`, `decision_engine.py`) بعد التعديل، مش بس الكود الجديد.
2. **تعديل مقترح على `verified_expression.py`** (تحويل `request_verified_expression`/`send_active_expression` من "بحث قاموس مباشر" إلى "orchestration لخط أنابيب كامل Truth→Meaning→Companionship→Validate") -- هذا **يمس مباشرة الضمان الرسمي الثلاثي المعتمد في مرحلة 6/7** (Information Containment / Verbatim Match Validator / Evidence Trace). أي دمج هنا لازم إثبات أن الضمانات الثلاثة القديمة إما (أ) لا تزال قائمة بنفس القوة تحت التصميم الجديد، أو (ب) استُبدلت بضمانات موازية بنفس الصرامة -- **هذا قرار حوكمة، مش تفصيلة تنفيذية**، ويستحق نفس مستوى المراجعة اللي أخذته قرارات مرحلة 6/7 الأصلية.
3. **تصادم مفاهيمي محتمل في التسمية**: `expression_vocabulary.py` (القاموس المقفول، مرحلة 6/7) مخطط له أن "يتبقى بدون حذف" ليصبح "Level-1 Fallback" -- هذا منطقي ومطمئن (لا حذف)، لكن يستحق التأكيد الصريح وقت الدمج الفعلي إن الاستخدام الحالي (المسار الوحيد اليوم) لا يُعطَّل بالخطأ أثناء أي مرحلة انتقالية.
4. **`Expression` record schema** (Firestore) مخطط له توسّع جوهري (`truth_packet_id`, `meaning_packet_id`, `companionship_text` بدل `template_key`/`rendered_text` الثابتين) -- أي دمج فعلي يحتاج خطة توافق (backward compatibility) مع أي سجلات قديمة، أو قبول أن السجلات القديمة والجديدة لهما شكل مختلف.

**لا شيء من هذه المخاطر الأربعة نُفِّذ فعليًا -- كلها في مرحلة التخطيط المكتوب فقط**، لكنها تستحق أن تكون على الطاولة صراحة قبل أي موافقة على دمج مستقبلي.

---

## 4. التصنيف الرباعي المطلوب

| العنصر | التصنيف | السبب |
|---|---|---|
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md` (v1) | **design only** | تصميم/pseudocode، أجزاء منه متجاوزة بـ v2 |
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` | **design only** (مع أجزاء منفّذة موثقة في مستندات Phase1 المنفصلة) | يحتوي قرارات معتمدة نظريًا وأسئلة لسه مفتوحة (قسم "القرارات المطلوبة منك" في آخره لم تُجَب) |
| `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` | **design only** | مسودة صراحة، تعيد فتح قرار مقفول سابقًا، تنتظر قرارك |
| `services/truth_layer.py` + `test_truth_layer.py` | **safe to integrate** (بشرط) | كود مكتمل، مختبر فعليًا (10/10)، معزول تمامًا (قراءة فقط، صفر اعتماديات على أي كود إنتاج)، صفر مخاطرة إن تُرك كما هو بدون ربط. **آمن للدمج التقني**، لكن الدمج الفعلي (ربطه بمسار حي) يفتح النقطة رقم 1 في قسم 3 |
| `services/meaning_layer.py` + `test_meaning_layer.py` | **safe to integrate** (بنفس الشرط) | نفس المنطق -- كود مكتمل ومختبر (12/12)، معزول، لا كتابة بيانات |
| `services/renderer.py` + `test_renderer.py` | **safe to integrate** (بنفس الشرط) | كود مكتمل ومختبر (10/10)، معزول تمامًا، صفر اعتماديات خارجية حتى |
| `services/claim_validator.py` (+ `test_claim_validator.py`) | **implementation draft (غير مكتمل -- Red state)** | الاختبارات مكتوبة (11) لكن الوحدة نفسها غير موجودة. **لا يمكن تصنيفه "safe to integrate" لأنه غير موجود أصلًا** |
| `services/inference_rules.py`, `services/companionship_layer.py`, `services/decision_trace.py`, `CONSTITUTION.md` | **needs redesign/not started** | لا يوجد كود إطلاقًا، مجرد بنود مخطط لها في المستندات. `companionship_layer.py` تحديدًا (الاستدعاء الوحيد لـ LLM في الـ pipeline) يستحق تصنيف "needs redesign" وليس مجرد "لم يبدأ"، لأن التوتر الجوهري الموصوف في `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` (حرية الصياغة مقابل الضمان الحتمي) لم يُحسم بعد -- وتصميم Companionship نفسه يعتمد على نتيجة ذلك القرار |
| التعديلات المقترحة على `self_state_engine.py` و`verified_expression.py` (مرحلة 1-7 القائمة) | **needs redesign / needs governance review** | كما في قسم 3 -- تعديل على عقد كود معتمد ومختبر بالكامل، يستحق نفس صرامة المراجعة التي أُعطيت لقرارات مرحلة 6/7 الأصلية قبل أي تنفيذ |

---

## 5. الخلاصة

- **لا يوجد تعارض فعلي حي** بين الطبقتين اليوم -- الفصل التام مؤكد بالفحص، ليس بالافتراض.
- **3 من 7 وحدات كود مخطط لها منفّذة فعليًا ومختبرة بالكامل** (Truth, Meaning, Renderer) -- جودة عالية، منهجية Tests First حقيقية وموثّقة.
- **وحدة واحدة في حالة توقف منتصف الطريق** (Claim Validator -- اختبارات موجودة، تنفيذ غائب).
- **3 وحدات + مستند حوكمة لم يبدأ العمل عليها إطلاقًا** (Inference Rules, Companionship Layer, Decision Trace, Constitution).
- **أهم قرار حوكمة معلّق قبل أي دمج**: التوتر بين "حرية الصياغة" و"الضمان الحتمي 100%" (موضوع `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md`) -- هذا يمس مباشرة الضمان الرسمي الثلاثي المعتمد في مرحلة 6/7، ولا ينبغي حسمه ضمنيًا أثناء بناء `companionship_layer.py` لاحقًا، بل كقرار مستقل صريح أولاً.

**لم يتم تنفيذ أي دمج أو migration في هذا الفحص، بالتصريح، وفي انتظار خطة اعتماد واضحة منك.**
