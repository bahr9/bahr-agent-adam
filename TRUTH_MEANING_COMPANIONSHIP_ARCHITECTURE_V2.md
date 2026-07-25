# Truth → Meaning → Companionship -- Architecture v2 (مراجعة وحسم)
تاريخ: 2026-07-24
الحالة: **تعديل جوهري على التصميم v1 بناءً على مراجعة معمارية دقيقة.** لسه مفيش كود.
المرجع: [TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md](TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md) (v1 -- الأجزاء اللي متغيرتش لسه صالحة، هنشاور عليها)

---

## ملخص التغيير الجوهري

المراجعة كشفت حاجتين أساسيتين غيّروا التصميم فعليًا، مش تحسينات تجميلية:

1. **الـ Meaning Layer معندهاش أي داعي يكون LLM خالص** -- هي عملية فلترة وترتيب بحتة على بيانات الـ backend يملكها بالفعل. شيلها بيقلل استدعاء LLM كامل من الـ pipeline.
2. **الحل الحقيقي لمشكلة "Companionship بتشوف أرقام خام" مش "نتحقق من الأرقام بعد ما تتكتب"، هو "الموديل ميكتبش رقم أصلاً"** -- تصميم Slot-Based Rendering: الموديل بيكتب نص فيه *مراجع* (placeholders)، والـ backend هو اللي بيملأ القيم الحقيقية. ده بيحل نص من نقاط المراجعة دفعة واحدة (الأرقام، نصوص الاستنتاجات المعتمدة بما فيها النفي جواها، والتقريب/التردد).

المعمارية الجديدة:

```
Constitution (مرجعي/توثيقي -- مش طبقة تشغيل، قسم 9)
    ↓
Truth Layer (Backend, حتمي)          -- زي v1، بتعديل على تمثيل المصادر (قسم 10.1)
    ↓
Meaning Layer (Backend, حتمي بالكامل -- بدون LLM)   -- كانت LLM Call #1 في v1
    ↓
Companionship Layer (LLM -- الاستدعاء الوحيد المتبقي في الـ pipeline كله)
    ↓  بتخرج: نص فيه Slots، مش نص نهائي بأرقام
Renderer (Backend, حتمي)              -- جديد -- بيملأ الـ Slots بالقيم الحقيقية
    ↓
Claim Validator (حتمي جزئيًا / heuristic جزئيًا -- محدود النطاق أكتر من v1)
    ↓
Decision Trace + Evidence Trace (الاتنين سوا)
    ↓
الرسالة النهائية
```

---

## الرد على النقاط العشر

### 1. هل الـ Meaning Layer محتاجة LLM؟ -- **موافق تمامًا، اتشالت**

صح 100%. `referenced_facts` و`fired_inferences` بيتحددوا من: (أ) الـ dimension اللي اتطلب أصلًا (معروفة قبل ما Meaning تشتغل خالص -- إما الموديل الرئيسي حددها في `request_verified_expression(dimension)`، أو الـ Active job حددها من `decision_engine`)، و(ب) نتيجة `evaluate_fired_rules(truth_packet)` (حتمية أصلًا من v1). مفيش "فهم" أو "استنتاج" حقيقي بيحصل هنا -- **عملية فلترة وترتيب بحتة**.

```python
# services/meaning_layer.py -- بقت بالكامل بدون LLM

def compute_meaning_packet(truth_packet: TruthPacket, target_dimension: str, fired_rules: list[dict]) -> dict:
    relevant_facts = {f.field: f.value for f in truth_packet.facts if f.field.startswith(target_dimension)}
    relevant_inferences = [r for r in fired_rules if r["domain"] == truth_packet.domain]

    return {
        "referenced_facts": relevant_facts,
        "fired_inferences": relevant_inferences,
        "primary_focus": target_dimension,
        "confidence": truth_packet_confidence(truth_packet),  # قسم 6
        "allowed_topics": [target_dimension],  # allowlist صريحة -- مش blocklist (أأمن)
    }
```

**الأثر:** استدعاء LLM واحد اتشال من الـ pipeline بالكامل. تعقيد أقل، تكلفة أقل، **وسطح خطأ أقل** -- بالظبط زي ما لاحظت.

### 2. Meaning Packet محدود -- **موافق، اتوسّع**

بما إن Meaning بقت backend بحت (نقطة 1)، إضافة حقول زيادة بقت آمنة ورخيصة (مفيش مخاطرة LLM إضافية):

```python
MeaningPacket = {
    "referenced_facts": {"unresolved_conflict.count": 3, "unresolved_conflict.level": "high"},
    "fired_inferences": [{"rule_id": "unresolved_conflict_high", "text": "...", "claims": [...]}],  # قسم 10.2
    "primary_focus": "unresolved_conflict",
    "secondary_focus": [],           # لو أكتر من بُعد اتطلب مرة واحدة
    "priority_order": ["unresolved_conflict"],   # حسب severity ranking ثابت في الـ backend
    "confidence": "full",            # full | degraded -- قسم 6
    "allowed_topics": ["unresolved_conflict"],    # allowlist -- ده اللي Claim Validator بيتأكد منه
}
```

`priority_order` بيتحدد بجدول severity ثابت في الـ backend (زي: `unresolved_conflict > pending_obligation_load > tracking_stability` -- ترتيب مقترح، **محتاج تأكيدك** مش قرار نهائي مني).

### 3. Companionship لسه بتشوف قيم خام -- **موافق، وده أهم تعديل في المراجعة كلها**

**الحل: Slot-Based Rendering.** Companionship بتكتب نص فيه *مراجع بالاسم*، مش قيم:

```python
# ناتج Companionship (LLM) -- مش النص النهائي
"يا بحورة، لقيت {unresolved_conflict.count} حالات تعارض لسه معلّقة، و{inference:unresolved_conflict_high}."
```

```python
# services/renderer.py -- جديد، حتمي بالكامل
def render(template: str, meaning_packet: dict) -> str:
    text = template
    for field, value in meaning_packet["referenced_facts"].items():
        text = text.replace(f"{{{field}}}", str(value))
    for inf in meaning_packet["fired_inferences"]:
        text = text.replace(f"{{inference:{inf['rule_id']}}}", inf["text"])
    return text
```

**الأثر المباشر:** الموديل **ميكتبش رقم ولا نص استنتاج بنفسه خالص** -- بيكتب بس اسم مرجع. أي رقم أو جملة استنتاج نهائية جايين حرفيًا من الـ backend. ده بيحل مباشرة:
- مشكلة الأرقام المخترعة (مفيش رقم يتكتب من الموديل أصلًا).
- مشكلة النفي جوه الاستنتاجات المعتمدة (قسم 10.2 تحت).
- جزء كبير من مشكلة التقريب/التردد (قسم 10.3 تحت) -- "3 أو 4" مستحيل تتكتب لأن الأرقام مش موجودة كنص حر خالص.

الحرية الأسلوبية باقية **بالكامل** -- ترتيب الجملة، النبرة، الكلام حوالين الـ slots، الافتتاحية/الخاتمة -- كل ده حر تمامًا. اللي اتقيّد هو *مصدر الحقائق*، مش الأسلوب.

### 4. Claim Validator محتاج تحليل دلالي أعمق (معظم/أغلب/قليل/زاد) -- **موافق، على خارطة الطريق، مش الآن**

اتسجل رسميًا كبند مستقبلي: **Semantic Claim Representation / AST بدل Regex بحت**. ملحوظة مهمة: تصميم الـ Slots (نقطة 3) بيقلل إلحاحية المشكلة دي جزئيًا للكميات (مفيش رقم خام يتلاعب بيه أصلًا)، لكن كلمات زي "معظم"/"زاد" لسه ممكن تتضاف كوصف حر حوالين الـ slot وتغيّر المعنى الكمّي بدون ما تلمس الرقم نفسه -- المشكلة دي حقيقية ومش متحلة بالكامل بتصميم v2. **مسجّلة في قسم "خارطة الطريق" آخر المستند، مش متجاهلة.**

### 5. إدارة قواعد الاستنتاج عند التوسع (Rule Engine, Priority, Conflict Resolution, Versioning) -- **موافق جزئيًا، تحفظ على التوقيت**

الاقتراح صح للمستقبل، لكن نطاقنا الحالي (الأقساط، 3 قواعد) بيخلي بناء Rule Engine كامل دلوقتي over-engineering -- نفس المبدأ اللي مشينا بيه من أول المشروع ("نطاق ضيق أول، اتأكد إنه شغال، بعدين وسّع" -- زي `tracking_stability` في 5.1، وزي تأجيل الـ Heuristic Scanner في مرحلة 6/7).

**الحل الوسط المقترح:** نضيف حقلين رخيصين للقواعد دلوقتي (`priority: int`, `version: str`) -- بيكلفوا صفر تقريبًا وبيسهّلوا أي Rule Engine مستقبلي، لكن من غير ما نبني آلية conflict resolution كاملة قبل ما نحتاجها فعليًا:

```python
{
    "rule_id": "unresolved_conflict_high",
    "domain": "loans",
    "priority": 10,     # جديد -- رقم أعلى = أولوية أعلى
    "version": "v1",    # جديد -- زي computation_version في TruthFact
    "condition": lambda facts: facts.get("unresolved_conflict.level") == "high",
    "text": "الوضع محتاج مراجعة عاجلة",
    "claims": [...],    # قسم 10.2
}
```

لو عدد القواعد وصل لعشرات فعليًا (مش نظريًا)، وقتها نبني Rule Engine حقيقي بمعزل. دلوقتي التحضير كافي.

### 6. مفهوم الـ Confidence -- **موافق، اتضاف**

```python
def truth_packet_confidence(packet: TruthPacket) -> str:
    return "degraded" if packet.integrity["partial"] else "full"
```

- **Truth Confidence**: مباشرة من `integrity.partial` (موجود أصلًا من v1، دلوقتي بقى له اسم صريح).
- **Meaning Confidence**: بما إن Meaning بقت دالة حتمية بحتة فوق Truth (نقطة 1)، **مفيش عدم يقين إضافي بيتولّد فيها** -- بترث نفس قيمة Truth Confidence مباشرة، صفر حساب إضافي.
- **Expression Confidence**: من نتيجة الـ Claim Validator -- `"verified"` (عدّى من أول مرة) / `"verified_after_retry"` / `"fallback"`.

**قرارات مبنية على الثقة (زي ما اقترحت بالظبط):**
- `truth_confidence == "degraded"` → **الـ Active ممنوعة تمامًا** لأي بُعد جزء منه ناقص (مش نطلب من النظام يبادر بحاجة مش متأكد منها بالكامل).
- `truth_confidence == "degraded"` في Passive → يرجع `verified=false` (وصف النقص، زي القاعدة الأصلية من مرحلة 6/7) بدل محاولة تعبير جزئي.

### 7. بروتوكول إعادة التوليد -- **بالفعل زي ما اقترحت، من v1**

التصميم الأصلي (v1، قسم 6) كان بالفعل: Active = صفر إعادة محاولة، نزول مباشر لـ Fallback. Passive = محاولة واحدة بس. **مفيش تغيير هنا -- كان صح من الأول، وده تأكيد مش تعديل.**

### 8. Decision Trace -- **موافق، ناقص حقيقي، اتضاف**

```python
DecisionTrace = {
    "decision_id": "uuid",
    "dimension": "unresolved_conflict",
    "trigger_type": "active" | "passive",
    "decided_at": "ISO timestamp",
    "reason": "level_transitioned_to_high" | "level_unchanged_suppressed" | "user_asked",
    "previous_level": "elevated",   # لو active
    "current_level": "high",
    "outcome": "expressed" | "suppressed_cooldown" | "suppressed_low_confidence",
    "expression_id": "..." or None,  # لو أدّت لتعبير فعلي
}
```

بيتسجل من `decision_engine.decide_expression` (اللي أصلًا بيحسب `transitioned` -- Stage 5 -- بس مبيسجّلش النتيجة كـ trace دائم). التسجيل هيحصل عند: كل قرار Active (اتكلم أو اتقمع)، وكل طلب Passive. الفحوصات الروتينية اللي "مفيش فيها جديد خالص" (الـ job الساعي بيلاقي نفس الحالة زي قبل) هتفضل log بس (مش Firestore) -- تسجيل كل ساعة من غير تغيير هيضخّم البيانات من غير قيمة حقيقية.

### 9. فين الدستور؟ -- **موافق مبدئيًا، لكن بصفته توثيقي مش طبقة تشغيل**

الدستور مش "طبقة" بمعنى إنه بيعالج بيانات زي Truth/Meaning/Companionship -- هو **مجموعة قيود لازم كل طبقة تلتزم بيها بالتصميم**. الشكل التقني المقترح: ملف مرجعي واحد (`CONSTITUTION.md`) بيجمع كل المبادئ السبعة المعتمدة لحد دلوقتي، وبيربط كل واحد **بالآلية الفعلية اللي بتفرضه في الكود**:

| المبدأ | آلية الفرض الفعلية |
|---|---|
| "لا يجوز لآدم أن يعبّر عن حالة داخلية ما لم تكن مبنية على دليل" | `TruthFact` إجباري evidence_event_ids أو static_schedule -- `build_truth_fact` بيرفض بدونه |
| "الحالة نتيجة حسابية قابلة للتفسير" (5) | `self_state_engine.py` قواعد Python صريحة، صفر LLM |
| "كل ما زادت المبادرة قلّت الحرية" (6) | Active = صفر retry + Fallback حتمي، Passive = retry واحد |
| "آدم يفكر في الحقائق، ميخترعش حقائق جديدة" (7) | Slot-Based Rendering + Claim Validator (v2 كله) |

ده بيخلي الرسم البياني اللي رسمته (Constitution → Truth → Meaning → Companionship) **صحيح فعليًا كتسلسل توثيقي**، حتى لو مش كل صف فيه "طبقة تشغيل" بمعنى pipeline stage.

---

## 10. النقاط التلاتة المعلّقة -- حسم مباشر (دي كانت أدق حاجة في المراجعة)

### 10.1 تضارب تمثيل المصادر -- باگ حقيقي في مثال v1، اتصلح

كنت غلط في المثال -- `count=7` بدليل `evidence_event_ids=["e4"]` (واحد بس) كان هيفشل فحص التناسق بتاعي أنا. السبب الجذري: `pending_obligation_load.count` مش علاقة 1:1 بسيطة مع الأحداث (زي `unresolved_conflict.count` اللي فعلاً كل تعارض = حدث واحد) -- أغلب الأقساط المتأخرة "متأخرة" لغياب أي حدث دفع، مش لوجود حدث صريح.

**الحل: نوعين مصدر إضافيين + مفهوم "derived":**

```python
FactSource = Literal["event_evidence", "static_schedule", "derived"]

TruthFact(
    field="pending_obligation_load.overdue_items",
    type="list",
    value=[
        {"identity_key": "valu_0", "has_explicit_event": False},
        {"identity_key": "ca_5", "has_explicit_event": True, "evidence_event_ids": ["e4"]},
        # ...
    ],
    source="static_schedule",   # الأساس هو الجدول الثابت + غياب حدث دفع
    evidence_event_ids=["e4"],  # اتحاد أي أحداث حقيقية موجودة فعلًا عبر العناصر (ممكن تكون فاضية)
),
TruthFact(
    field="pending_obligation_load.count",
    type="integer",
    value=7,
    source="derived",
    derived_from_field="pending_obligation_load.overdue_items",  # حقل جديد -- إجباري لو source="derived"
    evidence_event_ids=[],  # الحقول المشتقة مالهاش دليل خاص بيها -- بترث من اللي اشتُقت منه
)
```

**فحص التناسق الجديد (بدل القاعدة العمياء `count == len(evidence)`):**
```python
def validate_truth_packet(packet: TruthPacket) -> list[str]:
    errors = []
    facts_by_field = {f.field: f for f in packet.facts}
    for fact in packet.facts:
        if fact.source == "event_evidence" and not fact.evidence_event_ids:
            errors.append(f"{fact.field}: event_evidence بدون دليل")
        if fact.source == "derived":
            if not fact.derived_from_field or fact.derived_from_field not in facts_by_field:
                errors.append(f"{fact.field}: source=derived لازم derived_from_field يشاور لحقل موجود فعليًا في نفس الـ packet")
    return errors
```

**صراحة:** التحقق ده بيتأكد إن الحقل المصدري *موجود*، مش إن العملية الحسابية (`count == len(list)`) *صحيحة رياضيًا* -- التحقق من صحة الحساب نفسه لسه مسؤولية دالة `compute_*` (زي أي كود تاني)، مش الـ schema. توسيع أكتر من كده (تحقق صيغة حسابية عامة) over-engineering دلوقتي.

### 10.2 النفي جوه الاستنتاج المعتمد -- **اتحل بنيويًا عبر Slot-Based Rendering (نقطة 3)**

مع التصميم الجديد، السؤال بيتغيّر: النفي "مش مؤشر مشكلة" **مبيتكتبش من الموديل خالص** -- هو نص ثابت جوه `fired_inferences[].text` بيتحط في مكانه عبر `{inference:frequent_corrections_neutral}` وقت الـ Render. الموديل بيحط اسم المرجع بس. يبقى:
- ✅ النفي المعتمد (جوه نص الـ rule) آمن 100% -- مبيتولّدش من LLM أصلًا، بيتلصق حرفيًا.
- ❌ أي نفي **حر** يضيفه الموديل بنفسه حوالين الـ slot (مش جوّاه) لسه لازم يتفحص -- هنا `scan_negation_and_comparison` (heuristic، زي ما هو) بيفضل شغال، لكن نطاقه بقى أضيق بكتير (بس النص الحر حوالين الـ slots، مش الجملة كلها).

كمان بتبنّى اقتراحك عن الـ Claim Representation الصريحة للقواعد -- مضافة في نقطة 5 فوق (`claims` field في كل rule)، مفيدة لأي تحقق دلالي مستقبلي (نقطة 4).

### 10.3 التقريب والصياغات المترددة حول أرقام مؤكدة -- **جزء كبير اتحل بنيويًا، والباقي heuristic موثّق**

مع Slot-Based Rendering: "3 أو 4" **مستحيل تتكتب** لأن الأرقام مش نص حر أصلًا -- كتابة رقم خام برّه الـ slot بتترفض فورًا (فحص حتمي: أي digit في ناتج Companionship خارج صيغة `{field}` = رفض تلقائي، بدون استثناء).

**الباقي (كلمة تقريب لاصقة بالـ slot، زي "حوالي {count}"):** لسه ممكنة، ومحتاجة فحص إضافي زي ما اقترحت بالظبط:

```python
APPROXIMATION_PATTERNS = [r"حوالي", r"تقريبًا", r"يمكن", r"غالبًا", r"في\s+حدود"]

def check_certainty_violation(companionship_template: str, meaning_packet: dict) -> list[str]:
    """heuristic -- بيفحص وجود كلمة تقريب قريبة من أي slot مصدره exact."""
    errors = []
    for pat in APPROXIMATION_PATTERNS:
        for m in re.finditer(pat, companionship_template):
            nearby = companionship_template[max(0, m.start()-15):m.end()+15]
            if re.search(r"\{[\w.]+\}", nearby):  # فيه slot قريب من كلمة التقريب
                errors.append(f"كلمة تقريب '{pat}' جنب slot -- الحقيقة الأصلية exact مش approximate")
    return errors
```

**وإضافة `certainty` كحقل صريح في الـ Schema (زي ما اقترحت):**
```python
TruthFact(..., certainty="exact")   # كل حقائقنا الحالية exact -- معدودة من events/جدول ثابت
```
لو حقيقة مستقبلية كانت أصلًا تقريبية (`certainty="approximate"`)، كلمات التقريب حواليها تبقى مقبولة -- الفحص بيقارن `certainty` المصدر، مش يمنع التقريب مطلقًا.

**تصنيف صريح:** ده **heuristic**، مش حتمي 100% (الفحص بالقرب النصي، مش تحليل دلالي كامل). موثّق كده بصراحة في الجدول الصادق تحت.

---

## الجدول الصادق المُحدّث (Deterministic / Heuristic / Probabilistic)

| الفحص | v1 | v2 | التغيير |
|---|---|---|---|
| تطابق Meaning↔Truth | حتمي (بعد تحقق LLM output) | **حتمي (مفيش LLM أصلًا -- الفلترة نفسها الكود)** | أقوى -- مفيش LLM يُتحقق منه، الكود بيحسبه مباشرة |
| الأرقام في النص النهائي | حتمي (regex match) | **حتمي وأقوى (الأرقام مش نص حر أصلًا -- slots بس)** | أقوى جدًا -- المشكلة اتلغت مش اتحلت |
| نصوص الاستنتاجات المعتمدة (بما فيها نفي) | heuristic (scan على النص كله) | **حتمي (نص ثابت يتلصق، مش يتولّد)** | أقوى -- نفس منطق الأرقام |
| التقريب/التردد | مش موجود في v1 | **heuristic جديد (قسم 10.3)** | إضافة حقيقية |
| كلمات كمية غامضة (معظم/أغلب) | مش مغطاة | **لسه مش مغطاة -- خارطة طريق (نقطة 4)** | بدون تغيير، موثّق بصراحة |
| السببية/التنبؤات/الوعود | ممنوعة بنيويًا (Meaning مالهاش بُعد زمني) | **زي v1 بالظبط -- التبرير نفسه لسه صالح** | بدون تغيير |

---

## خارطة الطريق (بنود مؤجّلة عمدًا، موثّقة مش متجاهلة)

1. Semantic Claim Representation / AST بدل Regex (نقطة 4) -- لحد ما نشوف احتياج فعلي بعد الكميات الغامضة.
2. Rule Engine كامل بـ Conflict Resolution (نقطة 5) -- لحد ما عدد القواعد يوصل لعشرات فعليًا.
3. تحقق حسابي كامل لصحة الـ `derived` facts (نقطة 10.1) -- دلوقتي بنتأكد من الربط بس، مش صحة العملية الحسابية.

---

## أثر التعديلات على خطة التنفيذ (v1 قسم 8)

- `services/meaning_layer.py`: بقت بدون LLM -- أبسط، أسرع اختبار (unit tests بحتة، مفيش حاجة لـ mock LLM calls).
- `services/renderer.py`: **ملف جديد** -- الجزء الحتمي اللي بيملأ الـ slots.
- `services/claim_validator.py`: نفس الملف، لكن الفحص الرقمي بقى أبسط (رفض أي digit خارج slot، مش matching معقّد) + إضافة `check_certainty_violation`.
- `services/inference_rules.py`: كل rule بتاخد `priority`, `version`, `claims` إضافيين.
- `services/decision_trace.py`: **ملف جديد** -- تسجيل قرارات التعبير (نقطة 8).
- `CONSTITUTION.md`: **ملف توثيقي جديد** -- مرجع المبادئ وربطها بآليات الفرض (نقطة 9).
- مراحل الـ Migration (v1 قسم 8) **زي ما هي بالظبط** -- التعديلات هنا داخل نفس المراحل، مفيش مرحلة إضافية جديدة.

---

## القرارات المطلوبة منك

1. `priority_order` الافتراضي للأبعاد (`unresolved_conflict > pending_obligation_load > tracking_stability`) -- موافق ولا ترتيب تاني؟
2. الدستور (`CONSTITUTION.md`) -- ملف مستقل جديد، ولا يتدمج مع مستند موجود؟
3. موافق نبدأ التنفيذ الفعلي دلوقتي بالمرحلة 1 المعدّلة (`truth_layer.py` بتمثيل المصادر الجديد)؟
