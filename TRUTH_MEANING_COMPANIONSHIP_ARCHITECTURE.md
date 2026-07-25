# Truth → Meaning → Companionship — Architecture & Execution Plan
تاريخ: 2026-07-24
الحالة: **تصميم تنفيذي كامل، لسه مش متبني.** كل الـ schemas والـ pseudocode هنا حقيقية وقابلة للتنفيذ المباشر، لكن مفيش كود اتكتب في الإنتاج بعد -- التنفيذ نفسه مقسّم لمراحل في قسم 8.
المبدأ السابع (معتمد): "آدم يستطيع التفكير في الحقائق المثبتة، لكنه لا يستطيع إنشاء حقائق جديدة يُبنى عليها التفكير."

---

## ملخص تنفيذي -- قبل التفاصيل

السؤال الحاكم اتغيّر من "مين بيولّد النص؟" لـ "مين بيملك الحقيقة، مين بيفسّرها، مين بيعبّر عنها؟". الحل المعماري:

```
Truth Layer (Backend, حتمي بالكامل)
    │  Truth Packet: حقائق مسندة لدليل، مفيش قيمة من غير مصدر
    ▼
Meaning Layer (LLM Call #1 -- يخرج بيانات مبنية، مش نص حر)
    │  Meaning Packet: أي حقائق استُخدمت + أي استنتاجات معتمدة اتفعّلت
    │  [تحقق بنيوي حتمي: كل حاجة في الـ Meaning Packet لازم تكون فعلاً
    │   موجودة في الـ Truth Packet أو في قائمة الاستنتاجات المعتمدة]
    ▼
Companionship Layer (LLM Call #2 -- نص حر، لكن مبني على Meaning Packet
    │  المتحقق منه، مش على الحقائق الخام مباشرة)
    ▼
Claim Validator (استخراج + تحقق حتمي/heuristic حسب نوع الـ Claim)
    │  [رفض / إعادة توليد مرة / Fallback حتمي لمستوى القوالب]
    ▼
الرسالة النهائية + Evidence Trace كامل
```

**الفرق الجوهري عن التصميم السابق:** بدل "LLM يكتب نص حر من الحقائق الخام مباشرة" (اللي فيه مساحة تفسير غير محدودة)، فيه **خطوة بينية بنيوية (Meaning Packet)** بتحصر أي استخدام للحقائق في شكل قابل للتحقق الحتمي *قبل* ما أي نص حر يتكتب. الحرية الأسلوبية بتحصل في الخطوة الأخيرة بس، وعلى مدخلات مُتحقق منها فعلاً، مش على الحقائق الخام.

---

## 1. Truth Layer

### المصدر الحالي
**نفس البنية التحتية الموجودة بالضبط** -- `services/self_state_engine.py` (Stage 5) و `services/event_store.py` (Stage 1). مفيش إعادة بناء من الصفر. الـ Truth Layer طبقة **تغليف وتوثيق أصرم** حوالين نفس دوال الحساب (`compute_unresolved_conflict`, `compute_pending_obligation_load`, `compute_tracking_stability`) -- مش بديل ليها.

### Truth Packet Schema (فعلي، مش وصف عام)

```python
# services/truth_layer.py

from dataclasses import dataclass, field
from typing import Optional, Literal

FactType = Literal["integer", "enum", "boolean", "date", "string"]
FactSource = Literal["event_evidence", "static_schedule"]

@dataclass
class TruthFact:
    field: str                      # "unresolved_conflict.count"
    type: FactType                  # "integer"
    value: object                   # 3
    source: FactSource              # "event_evidence" أو "static_schedule"
    evidence_event_ids: list        # [] لو source == "static_schedule"، إلزامي لو "event_evidence"
    computed_by: str                # "self_state_engine.compute_unresolved_conflict"
    computation_version: str        # "v1" -- لو منطق الحساب اتغيّر، الرقم ده بيتغيّر

@dataclass
class TruthPacket:
    truth_packet_id: str            # uuid4
    domain: str                     # "loans"
    derived_at: str                 # ISO timestamp
    ttl_seconds: int                # 300 -- بعدها الـ packet يُعتبر stale
    facts: list                     # [TruthFact, ...]
    integrity: dict                 # {"computation_errors": [...], "partial": bool}
```

### مثال فعلي (Data Structure حقيقي، مش وصف)

```python
TruthPacket(
    truth_packet_id="a1b2c3d4-...",
    domain="loans",
    derived_at="2026-07-24T10:00:00+03:00",
    ttl_seconds=300,
    facts=[
        TruthFact(
            field="unresolved_conflict.count",
            type="integer",
            value=3,
            source="event_evidence",
            evidence_event_ids=["e1", "e2", "e3"],
            computed_by="self_state_engine.compute_unresolved_conflict",
            computation_version="v1",
        ),
        TruthFact(
            field="unresolved_conflict.level",
            type="enum",
            value="high",
            source="event_evidence",
            evidence_event_ids=["e1", "e2", "e3"],  # نفس الدليل -- level مشتق من نفس الأحداث
            computed_by="self_state_engine.compute_unresolved_conflict",
            computation_version="v1",
        ),
        TruthFact(
            field="pending_obligation_load.count",
            type="integer",
            value=7,
            source="event_evidence",
            evidence_event_ids=["e4"],  # أول قسط بس عنده حدث صريح -- الباقي مصدرهم الجدول الثابت (تحت)
            computed_by="self_state_engine.compute_pending_obligation_load",
            computation_version="v1",
        ),
    ],
    integrity={"computation_errors": [], "partial": False},
)
```

### منع القيم غير المثبتة من الدخول -- Builder بيرفض لا يفلتر

```python
def build_truth_fact(field, type_, value, source, evidence_event_ids, computed_by, computation_version="v1"):
    if source == "event_evidence" and not evidence_event_ids:
        raise InvalidTruthFactError(
            f"{field}: source=event_evidence لازم يكون له evidence_event_ids -- مفيش استثناء"
        )
    if source == "static_schedule" and evidence_event_ids:
        raise InvalidTruthFactError(
            f"{field}: source=static_schedule مينفعش يكون له evidence_event_ids (مصدره الجدول الثابت مش أحداث)"
        )
    if type_ == "enum" and "allowed_values" not in extra_kwargs:
        raise InvalidTruthFactError(f"{field}: نوعه enum لازم allowed_values محددة")
    return TruthFact(field, type_, value, source, evidence_event_ids, computed_by, computation_version)
```

**نفس فلسفة `event_store.InvalidEventError` بالضبط (Stage 1)**: الرفض يحصل وقت البناء، مش تنقية بعد كده. حقيقة من غير مصدر واضح **مستحيل توصل لـ TruthPacket خالص**.

### ربط كل Field بمصدره ووقته ودليله
كل `TruthFact` فيه الأربعة سوا: `computed_by` (مين حسبها) + `derived_at` (على مستوى الـ packet -- وقت الحساب) + `evidence_event_ids` (الدليل) + `computation_version` (لو منطق الحساب اتغيّر بعدين، نقدر نميّز الحقائق القديمة).

---

## 2. Truth Integrity

### كيف نتأكد إن الـ Truth Packet نفسه صحيح

**أ) تحقق بنيوي (حتمي 100%)** -- `validate_truth_packet(packet)`:
```python
def validate_truth_packet(packet: TruthPacket) -> list[str]:
    """يرجع قايمة أخطاء -- فاضية يعني الـ packet سليم بنيويًا."""
    errors = []
    for fact in packet.facts:
        if fact.source == "event_evidence" and not fact.evidence_event_ids:
            errors.append(f"{fact.field}: مفيش evidence رغم إن source=event_evidence")
        if fact.type == "enum" and fact.value not in fact.__dict__.get("allowed_values", []):
            errors.append(f"{fact.field}: القيمة {fact.value} مش من ضمن allowed_values")
    # تحقق تناسق: count لازم يطابق عدد evidence_event_ids لو العلاقة 1:1
    count_fact = next((f for f in packet.facts if f.field.endswith(".count")), None)
    if count_fact and count_fact.source == "event_evidence":
        if len(count_fact.evidence_event_ids) != count_fact.value:
            errors.append(f"{count_fact.field}: value={count_fact.value} لكن evidence_event_ids فيها {len(count_fact.evidence_event_ids)} -- تناقض")
    return errors
```

**ب) خطأ في Computed State -- إيه اللي بيحصل**
لو `self_state_engine.compute_unresolved_conflict()` فشلت (Firestore error مثلًا)، **الحل الحالي (Stage 5) كان بيرجع `[]` بصمت وبيسجّل log بس** -- ده بالظبط الفجوة اللي اتأجلت وقت مناقشة `computation_ok` في مرحلة 6/7. التصميم ده **بيقفلها إجباريًا**: أي دالة حساب لازم ترجع `(value, computation_ok: bool)` بدل القيمة لوحدها. لو `computation_ok=False`، الـ `TruthFact` المرتبطة **متتضافش للـ packet خالص**، و`packet.integrity["partial"] = True` و`packet.integrity["computation_errors"]` بتوصف السبب.

**ج) هل ممكن نكتشف حقائق متناقضة أو ناقصة؟**
نعم -- عبر `validate_truth_packet` (تناقض) + `integrity["partial"]` (نقص). أي طبقة تالية (Meaning) **ممنوع تستخدم packet فيه أخطاء بنيوية أو partial=True لبُعد هي محتاجاه** -- بترجع "verified=false" لنفس الفلسفة الموجودة أصلًا.

**د) بيانات قديمة/منتهية الصلاحية**
```python
def is_stale(packet: TruthPacket) -> bool:
    age = (now_cairo() - datetime.fromisoformat(packet.derived_at)).total_seconds()
    return age > packet.ttl_seconds
```
أي استخدام لـ Truth Packet (خصوصًا في Active، بعد أي تأخير) لازم يتأكد `not is_stale(packet)` -- لو stale، يُعاد الحساب من الصفر (مش نستخدم قيم قديمة). ده تعميم لمنطق "recheck وقت الإرسال" اللي كان موجود في `send_active_expression` أصلًا (Stage 6/7) -- بقى قاعدة عامة بدل حل خاص بالـ Active بس.

---

## 3. Meaning Layer

### إيه اللي بيتبعت للموديل، وإيه اللي لأ

**بيتبعت:**
- `TruthPacket.facts` (بس الحقول ذات الصلة بالسؤال/الحدث -- مش كل الـ Truth Layer دايمًا)
- `allowed_inferences`: قايمة الاستنتاجات المعتمدة اللي *فعّلت* شروطها فعليًا (من `inference_rules.py`، قسم 4) -- **مش كل قواعد الاستنتاج الممكنة**، بس اللي بقواعدها اتحققت دلوقتي.
- السياق (سؤال أحمد لو Passive، أو سبب التفعيل لو Active)

**مبيتبعتش:**
- أي event خام من `adam_events`
- أي بيانات من مجال تاني (Information Containment زي مرحلة 6/7 بالظبط)
- تاريخ المحادثة كامل (بس اللي محتاج للسياق المباشر)
- قواعد استنتاج **ماتفعّلتش** (عشان الموديل مايتأثرش بيها أو "يستوحي" منها حاجة مش حقيقية)

### الشكل: Structured JSON، والموديل بيخرج JSON مش نص

```python
MEANING_INPUT_SCHEMA = {
    "truth_packet": {"facts": [...]},  # زي المثال في قسم 1
    "allowed_inferences": [
        {"rule_id": "unresolved_conflict_high", "text": "الوضع محتاج مراجعة عاجلة"}
    ],
    "trigger": {"type": "passive", "user_question": "عامل إيه؟"}  # أو {"type": "active", "reason": "..."}
}
```

**الفرق الجوهري:** الموديل هنا **مبيكتبش رسالة نهائية** -- بيخرج **Meaning Packet** (بيانات مبنية):

```python
MEANING_OUTPUT_SCHEMA = {
    "referenced_facts": ["unresolved_conflict.count", "unresolved_conflict.level"],  # الحقول اللي فعلاً استخدمها
    "fired_inferences": ["unresolved_conflict_high"],  # من allowed_inferences بس، مفيش اختراع
    "requires_recommendation": False,
}
```

### الـ Prompt الفعلي (Meaning Layer، LLM Call #1)

```
أنت جزء من نظام آدم الداخلي -- مسؤوليتك الوحيدة: تحديد إيه الحقائق ذات
الصلة من اللي معاك، وإيه الاستنتاجات (لو موجودة) اللي تنطبق.

الحقائق المتاحة (الوحيدة المسموح تستخدمها):
{truth_packet_facts_json}

الاستنتاجات المعتمدة المتاحة (فعّلت شروطها فعليًا -- الوحيدة المسموح تشاور عليها):
{allowed_inferences_json}

السياق: {trigger_context}

طلب أحمد أو سبب التفعيل: استخدم بس اللي فوق. رجّع JSON بالشكل ده بالظبط:
{"referenced_facts": [...], "fired_inferences": [...], "requires_recommendation": bool}

ممنوع تضيف حقل، تخترع قيمة، أو تشاور على استنتاج مش موجود في القايمة.
ممنوع تكتب أي نص حر هنا -- الأسلوب مش شغلانتك في الخطوة دي.
```

### التحقق البنيوي (حتمي 100% -- خارج الـ LLM)

```python
def validate_meaning_packet(meaning_packet: dict, truth_packet: TruthPacket, fired_rule_ids: set) -> list[str]:
    errors = []
    valid_fields = {f.field for f in truth_packet.facts}
    for ref in meaning_packet["referenced_facts"]:
        if ref not in valid_fields:
            errors.append(f"referenced_facts فيها '{ref}' -- مش موجودة في truth_packet خالص")
    for inf in meaning_packet["fired_inferences"]:
        if inf not in fired_rule_ids:
            errors.append(f"fired_inferences فيها '{inf}' -- مش من ضمن القواعد اللي فعّلت فعليًا")
    return errors
```

**ده الجزء اللي بيرد على "لا أريد الاعتماد على الـ Prompt فقط" مباشرة:** التحقق ده set-membership check بسيط -- **حتمي 100%، قابل للاختبار الشامل**، مش heuristic. لو الموديل "اخترع" مرجع لحقيقة أو استنتاج مش موجود، بيترفض آليًا **قبل** ما يوصل لمرحلة الصياغة خالص.

---

## 4. Inference Policy

### تعريف صريح

- **استنتاج مسموح**: أي mapping من تركيبة حقائق لجملة تفسيرية، **معرّف مسبقًا في جدول قواعد بالـ backend**، وشرطه اتحقق فعليًا من الـ Truth Packet الحالي.
- **استنتاج غير مسموح**: أي حكم، تفسير، أو ربط سببي **مش موجود في الجدول**، حتى لو منطقي أو "بديهي" من وجهة نظر الموديل.

### من أين تأتي قواعد الاستنتاج -- ثابتة بالكامل في الـ Backend

```python
# services/inference_rules.py

INFERENCE_RULES = [
    {
        "rule_id": "unresolved_conflict_high",
        "domain": "loans",
        "condition": lambda facts: facts.get("unresolved_conflict.level") == "high",
        "text": "الوضع محتاج مراجعة عاجلة",
        "type": "interpretation",
    },
    {
        "rule_id": "obligation_concern",
        "domain": "loans",
        "condition": lambda facts: facts.get("pending_obligation_load.level") == "concern",
        "text": "فيه التزامات متراكمة محتاجة متابعة",
        "type": "interpretation",
    },
    {
        "rule_id": "frequent_corrections_neutral",
        "domain": "loans",
        "condition": lambda facts: facts.get("tracking_stability.level") == "frequent_corrections",
        "text": "معدل التصحيحات مرتفع -- ملاحظة موضوعية مش مؤشر مشكلة",
        "type": "interpretation",
    },
]

def evaluate_fired_rules(truth_packet: TruthPacket) -> list[dict]:
    """يرجع القواعد اللي شرطها اتحقق فعليًا -- دي بس اللي بتتبعت لـ Meaning Layer."""
    facts_map = {f.field: f.value for f in truth_packet.facts}
    return [r for r in INFERENCE_RULES if r["condition"](facts_map)]
```

**بيتمثّلوا إزاي:** جدول Python صريح، كل قاعدة شرط (`lambda` بسيط على قيم الحقائق) + نص معتمد. **مش الموديل بيستنتج -- الموديل بيختار من اللي اتفعّل فعليًا بس** (نفس فلسفة القاموس المقفول، بس على مستوى "معنى" مش "جملة كاملة").

**التحقق:** `validate_meaning_packet` فوق (قسم 3) -- `fired_inferences` لازم تكون subset من نتيجة `evaluate_fired_rules(truth_packet)`. حتمي 100%.

**هل ده بيمنع Meaning Layer من إنها تتحول لطبقة معرفة جديدة مع الوقت؟** نعم بالتصميم -- إضافة استنتاج جديد لازم تعديل كود صريح في `inference_rules.py` (مراجعة بشرية، commit، اختبار) -- مش شيء بيتولّد أو "يتعلّم" وقت التشغيل.

---

## 5. Companionship Layer

### أنواع الجمل

| النوع | مثال | مسموح بحرية؟ |
|---|---|---|
| **تعبير بحت** (Companionship) | "يا بحورة"، "خد بالك من نفسك"، ترتيب الجملة، النبرة | ✅ حر بالكامل |
| **Claim مرتبط بحقيقة** | "3 حالات تعارض" | ✅ لو الرقم يطابق `referenced_facts` في Meaning Packet |
| **Claim مرتبط باستنتاج معتمد** | "محتاج مراجعة عاجلة" | ✅ لو من `fired_inferences` |
| **Claim جديد (رقم/حالة/سبب/توقع/وعد)** | "5 حالات" (غلط)، "هيتزود الأسبوع الجاي"، "هعمل كذا"، "عشان إنت مقصّرت" | ❌ ممنوع مطلقًا |

### إزاي بيتمنع إدخال أرقام/حالات/توقعات/وعود/أحكام/أسباب جديدة

**Companionship مبيقراش الـ Truth Packet خالص -- بيقرا الـ Meaning Packet المتحقق منه بس:**

```python
COMPANIONSHIP_INPUT_SCHEMA = {
    "meaning_packet": {  # الناتج المتحقق منه من قسم 3، مش الـ Truth Packet الخام
        "referenced_facts": {"unresolved_conflict.count": 3, "unresolved_conflict.level": "high"},
        "fired_inferences": ["الوضع محتاج مراجعة عاجلة"],
    },
    "tone_context": "companion_warm",  # نبرة عامة، مش تفاصيل
}
```

بما إن Companionship معندهاش وصول للـ Truth Packet الخام أصلًا (Information Containment بترحّل لهنا برضه)، **مصدر أي رقم ممكن يقوله محصور فعليًا فيما هو موجود قدامه** -- ده بيقلل مساحة الاختراع بنيويًا، مش بس بالتعليمة.

**لكن ده لوحده مش كفاية** -- لسه ممكن الموديل "يزوّد" رقم من عنده حتى لو مش شايف غيره (زي ما أي LLM ممكن يعمل). عشان كده الـ Claim Validator (قسم 6) شرط لازم، مش اختياري.

---

## 6. Claim-Level Traceability -- الـ Pipeline الكامل

### الخطوات

```
1. استخراج الـ Claims من نص Companionship
2. تحويلها لـ Representation منظم: {"type": "number"|"comparison"|"negation"|"causal"|"prediction"|"promise", "raw_text": "...", "normalized_value": ...}
3. مطابقة كل Claim مع Meaning Packet (مش Truth Packet مباشرة -- أضيق وأدق)
4. رفض / إعادة توليد مرة واحدة (Passive) أو صفر إعادة (Active) / Fallback حتمي
5. تخزين Trace كامل لكل Claim
```

### الجزء الحتمي بالكامل -- استخراج وتحقق الأرقام

```python
# services/claim_validator.py
import re

ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# كلمات الأرقام العربية الشائعة (1-20) -- تغطية معروفة، مش شاملة
NUMBER_WORDS = {
    "واحد": 1, "اتنين": 2, "تلاتة": 3, "تلات": 3, "أربعة": 4, "اربعة": 4,
    "خمسة": 5, "ستة": 6, "سبعة": 7, "تمانية": 8, "تسعة": 9, "عشرة": 10,
    # ... يُكمل حسب الحاجة الفعلية
}

def extract_numeric_claims(text: str) -> list[int]:
    normalized = text.translate(ARABIC_INDIC_DIGITS)
    digit_claims = [int(m) for m in re.findall(r"\d+", normalized)]
    word_claims = [v for w, v in NUMBER_WORDS.items() if w in text]
    return digit_claims + word_claims

def validate_numeric_claims(text: str, meaning_packet: dict) -> list[str]:
    """حتمي 100% -- كل رقم في النص لازم يطابق قيمة حقيقية في referenced_facts."""
    allowed_numbers = {
        v for v in meaning_packet["referenced_facts"].values() if isinstance(v, int)
    }
    errors = []
    for claim in extract_numeric_claims(text):
        if claim not in allowed_numbers:
            errors.append(f"رقم '{claim}' مش موجود في الحقائق المرجعية {allowed_numbers}")
    return errors
```

**ملحوظة صادقة:** تغطية كلمات الأرقام (`NUMBER_WORDS`) محدودة بالقايمة المكتوبة -- رقم بصياغة مش متوقعة (نادر لأرقام صغيرة، لكن ممكن) هيفوت من الفحص ده. الجزء الرقمي بالأرقام الفعلية (`\d+`) **حتمي وكامل**؛ الجزء بالكلمات **حتمي للكلمات المُدرجة بس**.

### الجزء الـ Heuristic -- مقارنات ونفي (أنماط معروفة)

```python
NEGATION_PATTERNS = [r"مفيش\s+أي", r"معندوش", r"صفر\s+"]
COMPARISON_PATTERNS = [r"أكتر\s+من", r"أقل\s+من", r"زاد", r"قل"]

def scan_negation_and_comparison(text: str) -> list[str]:
    """heuristic -- بيلاحظ الأنماط المعروفة، مش ضمان شامل للغة الطبيعية."""
    flags = []
    for pat in NEGATION_PATTERNS:
        if re.search(pat, text):
            flags.append(f"نمط نفي محتمل: '{pat}' -- محتاج تأكيد يدوي لو تكرر")
    return flags
```

### الجزء الـ Probabilistic بطبيعته -- سببية/توقعات/وعود

**هنا الصدق الكامل مطلوب صراحة:** جمل زي "عشان كده هيحصل..."، "هعمل كذا الأسبوع الجاي"، "ده هيأثر على..." -- دي بنية سببية/تنبؤية/وعدية **مفيش طريقة تُثبت آليًا بشكل حتمي 100% إنها مش موجودة في نص حر عربي عام**، غير باستخدام تصنيف NLU (يعني LLM تاني أو classifier -- احتمالي هو نفسه).

**القرار المعماري المقترح (مش حل تقني، قرار نطاق):** Companionship Layer **ممنوعة بنيويًا من إنتاج الفئات دي أصلًا** -- مش لأننا هنمسكها بعد ما تتقال، لكن لأن الـ prompt والـ Meaning Packet المتاح ليها **مفيهوش وقت أصلًا** ("هيحصل"، "هيتزود لاحقًا") ولا أفعال وعد ("هعمل"). الـ Meaning Packet بيوصف حالة حالية بس (`referenced_facts` + `fired_inferences` -- الاتنين "الآن"، مفيش بُعد زمني مستقبلي في الـ schema خالص). فحص heuristic إضافي (قايمة أفعال وعد/مستقبل شائعة) موجود **كطبقة دفاع إضافية**، مش كضمان.

**ده تحويل مشكلة "غير قابلة للحل حتميًا" لمشكلة "محدودة النطاق بالتصميم"** -- بدل ما نحاول نتحقق من كل جملة سببية ممكنة، بنمنع الفئة دي من الظهور من الأساس عبر تضييق مدخلات Companionship.

### بروتوكول الفشل

```python
def generate_companionship_message(meaning_packet, tone_context, is_active: bool) -> dict:
    text = call_llm_companionship(meaning_packet, tone_context)
    errors = validate_numeric_claims(text, meaning_packet) + scan_negation_and_comparison(text)

    if not errors:
        return {"text": text, "status": "verified", "attempt": 1}

    if is_active:
        # Active: صفر إعادة محاولة -- نزول مباشر لـ Fallback (قسم 3.7 من المسودة السابقة، متبنّاة هنا)
        return {"text": render_level1_fallback(meaning_packet), "status": "fallback", "attempt": 1}

    # Passive: محاولة تانية واحدة بس مع تصحيح صريح
    text2 = call_llm_companionship(meaning_packet, tone_context, correction=errors)
    errors2 = validate_numeric_claims(text2, meaning_packet) + scan_negation_and_comparison(text2)
    if not errors2:
        return {"text": text2, "status": "verified_after_retry", "attempt": 2}

    return {"text": render_level1_fallback(meaning_packet), "status": "fallback", "attempt": 2}
```

### الجدول الصادق: حتمي / heuristic / probabilistic

| الفحص | النوع | التغطية |
|---|---|---|
| تطابق الأرقام الرقمية (`\d+`) | **حتمي 100%** | كامل لأي رقم مكتوب بأرقام |
| تطابق كلمات الأرقام العربية | **حتمي للمُدرج بس** | محدود بقايمة `NUMBER_WORDS` |
| `referenced_facts`/`fired_inferences` مطابقة (Meaning↔Truth) | **حتمي 100%** | set-membership، كامل |
| أنماط النفي/المقارنة | **Heuristic** | أنماط معروفة بس، مش شامل |
| السببية/التنبؤ/الوعود | **Probabilistic بطبيعته -- مُخفَّف بتضييق النطاق البنيوي، مش بالتحقق** | غير قابل للضمان الكامل بالتصميم الحالي، وده مذكور صراحة مش مُخفى |

---

## 7. مثال تنفيذ كامل -- Domain الأقساط

### 1) الحدث الأصلي
3 أحداث `conflict_status=pending` على `ca_71`, `ca_70`, `ca_69` (Credit Agricole).

### 2) Computed State
`unresolved_conflict = {level: "high", count: 3, evidence_event_ids: ["e1","e2","e3"]}`

### 3) Evidence
الأحداث التلاتة الفعلية في `adam_events`.

### 4) الرسالة الحالية (Stage 6/7، قاموس مقفول)
`"تنبيه: ظهر تعارض غير محلول يحتاج مراجعتك."`

### 5) Truth Packet
```python
TruthPacket(facts=[
    TruthFact("unresolved_conflict.count", "integer", 3, "event_evidence", ["e1","e2","e3"], "self_state_engine.compute_unresolved_conflict", "v1"),
    TruthFact("unresolved_conflict.level", "enum", "high", "event_evidence", ["e1","e2","e3"], "self_state_engine.compute_unresolved_conflict", "v1"),
])
```

### 6) مدخلات Meaning Layer
```python
{
    "truth_packet": {...},  # فوق
    "allowed_inferences": [{"rule_id": "unresolved_conflict_high", "text": "الوضع محتاج مراجعة عاجلة"}],
    "trigger": {"type": "active", "reason": "unresolved_conflict transitioned to high"}
}
```

### 7) خرج Meaning
```python
{"referenced_facts": ["unresolved_conflict.count", "unresolved_conflict.level"], "fired_inferences": ["unresolved_conflict_high"], "requires_recommendation": false}
```
✅ تحقق بنيوي: الاتنين موجودين فعلًا في المدخلات → عدّى.

### 8) خرج Companionship
`"يا بحورة، لقيت 3 حالات تعارض في الأقساط لسه معلّقة، وده حاجة محتاجة نظرة منك دلوقتي."`

### 9) استخراج الـ Claims
`extract_numeric_claims` → `[3]`. مفيش أنماط نفي/مقارنة.

### 10) نتيجة التحقق
`3 ∈ {3}` (من `referenced_facts["unresolved_conflict.count"]`) → ✅ Pass.

### 11) Evidence Trace النهائي
```
expression_id → meaning_packet_id → truth_packet_id → evidence_event_ids=["e1","e2","e3"]
```

### 12) الرسالة النهائية
`"يا بحورة، لقيت 3 حالات تعارض في الأقساط لسه معلّقة، وده حاجة محتاجة نظرة منك دلوقتي."`

---

### مثال فشل -- Claim مختلق

Companionship تولّد: `"يا بحورة، عندك 5 حالات تعارض، وده هيأثر على قدرتك على السداد الشهر الجاي."`

- استخراج الأرقام: `[5]`. `5 ∉ {3}` → **رفض فوري**.
- كمان "هيأثر... الشهر الجاي" جملة تنبؤية سببية -- مش موجودة في `fired_inferences` (اللي بس فيها "الوضع محتاج مراجعة عاجلة") → مؤشر إضافي (heuristic) على انحراف.
- **قبل الإرسال بالكامل**: النص بيترفض، يتسجل في `validation_result` بأسباب الرفض، ولو Active → فورًا Fallback لـ `render_level1_fallback` (نص من `expression_vocabulary.py` الموجود -- "تنبيه: ظهر تعارض غير محلول يحتاج مراجعتك."). لو Passive → محاولة تانية بتصحيح صريح ("الرقم الصح 3 مش 5، ومفيش أي تفسير عن السداد المستقبلي متاح ليك").

### تطبيق على Domain تاني (المشاريع) من غير تعديل جوهري

| المكوّن | بيتغيّر؟ | إيه اللي بيتغيّر |
|---|---|---|
| Truth Layer builder | ✅ | Truth Packet builder جديد بيقرا من Project Command API/Event Store (لسه مش موجودة -- تُبنى على نفس نمط Loan Command API) |
| Truth Packet Schema | ❌ | نفس `TruthFact` بالظبط (field/type/value/source/evidence) |
| Inference Rules | ✅ إضافة | صفوف جديدة في `INFERENCE_RULES` بـ `domain="projects"` -- نفس الجدول، مفيش بنية جديدة |
| Meaning Layer | ❌ | نفس الكود، نفس الـ prompt (بيانات مختلفة بس) |
| Companionship Layer | ❌ | نفس الكود تمامًا |
| Claim Validator | ❌ | نفس الآليات (أرقام/أنماط) تنطبق بغض النظر عن الـ domain |

**الثابت:** كل حاجة من Meaning Layer لغاية Claim Validator **domain-agnostic بالتصميم** -- زي ما Self-State نفسها كانت Domain-Independent من مرحلة 5. اللي بيتغيّر بس هو مصدر الـ Truth Packet والـ Inference Rules الخاصة بالمجال الجديد.

---

## 8. خطة التنفيذ

### الملفات

| الملف | جديد/معدّل | الدور |
|---|---|---|
| `services/truth_layer.py` | جديد | `TruthFact`, `TruthPacket`, `build_truth_fact`, `validate_truth_packet`, `is_stale` |
| `services/inference_rules.py` | جديد | `INFERENCE_RULES`, `evaluate_fired_rules` |
| `services/meaning_layer.py` | جديد | LLM Call #1 + `validate_meaning_packet` |
| `services/companionship_layer.py` | جديد | LLM Call #2 + بروتوكول الفشل/Fallback |
| `services/claim_validator.py` | جديد | `extract_numeric_claims`, `validate_numeric_claims`, `scan_negation_and_comparison` |
| `services/self_state_engine.py` | معدّل | كل دالة `compute_*` ترجع `(value, computation_ok)` بدل قيمة لوحدها (يقفل فجوة `computation_ok` المؤجّلة من مرحلة 6/7) |
| `services/verified_expression.py` | معدّل جوهريًا | `request_verified_expression`/`send_active_expression` بيبقوا orchestration بس: truth→meaning→companionship→validate، بدل lookup مباشر من القاموس |
| `services/expression_vocabulary.py` | يتبقى **بدون حذف** | يتحول لمصدر بيانات الـ Level-1 Fallback (`render_level1_fallback`) -- شبكة الأمان الحتمية الأخيرة |
| `config.py` | معدّل | مجموعتين جديدتين: `adam_truth_packets`, `adam_meaning_packets` |

### الـ Interfaces (توقيعات الدوال الأساسية)

```python
truth_layer.build_truth_packet(domain: str, fact_specs: list) -> TruthPacket
truth_layer.validate_truth_packet(packet: TruthPacket) -> list[str]
inference_rules.evaluate_fired_rules(packet: TruthPacket) -> list[dict]
meaning_layer.generate_meaning_packet(packet: TruthPacket, fired_rules: list, trigger: dict) -> dict
meaning_layer.validate_meaning_packet(meaning: dict, packet: TruthPacket, fired_ids: set) -> list[str]
companionship_layer.generate_message(meaning: dict, tone_context: str, is_active: bool) -> dict
claim_validator.validate_numeric_claims(text: str, meaning: dict) -> list[str]
claim_validator.scan_negation_and_comparison(text: str) -> list[str]
```

### تدفق البيانات (End-to-End)

```
verified_expression.request_verified_expression(dimension, chat_id)
  → truth_layer.build_truth_packet("loans", ...)   [يستخدم self_state_engine داخليًا]
  → truth_layer.validate_truth_packet(packet)       [لو فيه أخطاء → verified=false، توقف هنا]
  → inference_rules.evaluate_fired_rules(packet)
  → meaning_layer.generate_meaning_packet(...)       [LLM Call #1]
  → meaning_layer.validate_meaning_packet(...)       [لو فيه أخطاء → إعادة محاولة أو fallback]
  → companionship_layer.generate_message(...)        [LLM Call #2 + claim validation داخليًا]
  → تسجيل TruthPacket + MeaningPacket + Expression كامل
  → إرجاع النص للـ caller (Passive: للموديل الأساسي يلصقه؛ Active: يتبعت مباشرة)
```

### اللي هيفضل من الـ Active Job الحالي
`main.py::self_state_active_check_job` **هيكل الجدولة نفسه يفضل زي ما هو بالظبط** (كل ساعة، بينادي `decision_engine.decide_expression`). الفرق الوحيد: بدل ما ينادي `verified_expression.send_active_expression` (اللي كانت بترندر من القاموس مباشرة)، هينادي نفس الاسم لكن الدالة نفسها بقت orchestration للـ pipeline الجديد، **مع الحفاظ على قاعدة "صفر إعادة محاولة للـ Active"** (قسم 6).

### التغيير في Evidence Trace
`Expression` record بيتوسّع:
```python
Expression {
    expression_id, chat_id, sent_at, mode, verified,
    truth_packet_id,      # جديد -- بدل template_key
    meaning_packet_id,    # جديد
    companionship_text,   # النص الفعلي المُولّد (بدل rendered_text الثابت)
    validation_result,    # {"numeric_check": "passed", "attempt": 1, "status": "verified"}
}
```
`TruthPacket` و `MeaningPacket` بيتسجلوا في collections منفصلة (`adam_truth_packets`, `adam_meaning_packets`) بنفس منطق `StateSnapshot` الحالي (يتسجلوا وقت الاستخدام الفعلي بس، مش كل حساب).

### سياسة الـ Fallback
موصوفة بالكامل في قسم 6 -- **حتمية بالكامل**: `render_level1_fallback` بيستخدم `expression_vocabulary.py` الموجود فعلًا (مفيش حذف)، فالشبكة الأخيرة هي نفس الضمان القديم 100% اللي كان موجود قبل التصميم ده.

### خطة الـ Migration -- مراحل صغيرة، الإنتاج ما بيتغيرش دفعة واحدة

| المرحلة | المحتوى | التأثير على الإنتاج |
|---|---|---|
| **1** | بناء `truth_layer.py` (يغلّف `self_state_engine` الموجود) + `validate_truth_packet` | صفر -- مجرد طبقة جديدة، مش متربطة بحاجة |
| **2** | بناء `inference_rules.py` + اختبار `evaluate_fired_rules` معزول | صفر |
| **3** | بناء `meaning_layer.py` + `validate_meaning_packet` -- اختبار بـ LLM calls حقيقية، **لكن الناتج بيتسجل بس، مبيتبعتش لحد** (Shadow Mode) | صفر -- بيانات Shadow بس |
| **4** | بناء `claim_validator.py` -- اختبار وحدات مكثّف (كل سيناريوهات قسم 9) قبل أي ربط | صفر |
| **5** | بناء `companionship_layer.py` + الـ pipeline كامل في **Shadow Mode**: يتحسب الناتج الجديد، يتقارن بالناتج القديم (القاموس)، **القديم لسه اللي بيتبعت فعليًا** | صفر -- مراقبة/مقارنة بس |
| **6** | بعد فترة مراجعة (أحمد يشوف نتايج الـ Shadow Mode)، تحويل **Passive بس** للـ pipeline الجديد (فيه إنسان حاضر يصحح فورًا لو حصل خطأ) | تغيير حقيقي أول مرة، على Passive بس |
| **7** | بعد ما Passive يثبت استقراره، تحويل **Active** للـ pipeline الجديد (أعلى مخاطرة -- آخر خطوة) | تغيير على Active |

كل مرحلة بتتحقق فعليًا (زي كل مرحلة سابقة في المشروع ده) قبل ما التالية تبدأ.

---

## 9. الاختبارات

### Unit Tests
- `build_truth_fact` بترفض `source=event_evidence` من غير evidence.
- `validate_truth_packet` بتلاقط تناقض count/evidence_event_ids.
- `evaluate_fired_rules` بترجع بس القواعد اللي شرطها True.
- `extract_numeric_claims` بتلاقط أرقام بالعربي والإنجليزي وكلمات الأرقام المُدرجة.

### Integration Tests
- Pipeline كامل حقيقي (زي Stage 6/7): حدث حقيقي → Truth → Meaning → Companionship → رسالة نهائية، مع تنظيف كامل بعدها (نفس منهجية كل الاختبارات السابقة).

### Adversarial Tests (كل الحالات المطلوبة)

| # | السيناريو | النتيجة المتوقعة | الطبقة اللي بتمسكها |
|---|---|---|---|
| 1 | اختراع رقم | رفض | Claim Validator (حتمي) |
| 2 | تغيير رقم صحيح | رفض | Claim Validator (حتمي) |
| 3 | اختراع حالة (بُعد مش في الـ packet) | رفض | Meaning Validator (حتمي) |
| 4 | نفي حقيقة صحيحة | تحذير/مراجعة | Heuristic scan (مش حتمي -- موثّق) |
| 5 | توقع غير مثبت | ما بيتولّدش أصلًا (نطاق Companionship مقيّد) + heuristic scan شبكة أمان | تضييق بنيوي + heuristic |
| 6 | تهريب Claim في مزحة | استخراج الرقم بيمسكه بغض النظر عن النبرة | Claim Validator (حتمي للأرقام) |
| 7 | تعارض Meaning↔Truth | رفض عند التحقق البنيوي | Meaning Validator (حتمي) |
| 8 | تعارض Companionship↔Truth | رفض عند claim validation | Claim Validator |
| 9 | إعادة صياغة صحيحة لنفس الحقيقة | ✅ تعدّي | كل الطبقات |
| 10 | استنتاج مسموح | ✅ تعدّي | Meaning Validator |
| 11 | استنتاج غير مسموح | رفض | Meaning Validator (حتمي) |
| 12 | فشل الـ Validator | Fallback لمستوى القوالب الحتمي | بروتوكول الفشل |

---

## 10. معايير النجاح -- تقييم صادق مقابل كل واحد

| المعيار | تحقق إزاي | حدوده |
|---|---|---|
| صفر Unsupported Factual Claims | بتحقق للأرقام/الحقائق/الاستنتاجات عبر تحقق حتمي؛ للسببية/التوقعات عبر **تضييق نطاق بنيوي** مش تحقق | مش "صفر" بالتحقق المطلق لكل نوع كلام -- "صفر" عبر منع الفئة الخطيرة من الظهور أصلًا |
| كل Claim له Trace أو مصنّف Non-Factual | ✅ بالتصميم (Expression record كامل) | -- |
| مش الاعتماد على Prompt وحده | ✅ (Meaning/Claim validators كود حقيقي خارج الـ LLM) | الـ prompt لسه طبقة أولى مساعدة، مش الضمان |
| تنوع أسلوبي حقيقي | ✅ (Companionship حرة كاملة في الصياغة) | -- |
| إعادة بناء السبب من الـ Trace | ✅ (TruthPacket + MeaningPacket + validation_result كلهم متخزنين) | -- |
| قابلية تطبيق على domains تانية | ✅ (قسم 7 -- موضّح بالتفصيل) | يحتاج Command API/Event Store للمجال الجديد أولاً (زي الأقساط) |

---

## 11. الحدود الصريحة -- الإجابة المباشرة المطلوبة

**Deterministic فعلًا (100%، قابل للاختبار الشامل):**
- بناء وتحقق الـ Truth Packet (مصدر/دليل/تناسق).
- التحقق البنيوي بين Meaning Packet والـ Truth Packet (referenced_facts/fired_inferences).
- تطابق الأرقام المكتوبة بالأرقام (مش كلمات) في نص Companionship.
- Evidence Trace بالكامل.
- بروتوكول الـ Fallback نفسه (لو التحقق فشل، الانتقال لمستوى القوالب حتمي 100%).

**Heuristic (دفاع حقيقي، مش ضمان رياضي):**
- تطابق كلمات الأرقام العربية (محدود بقايمة معروفة).
- أنماط النفي والمقارنة.

**Probabilistic بطبيعته (غير قابل للضمان الحتمي بالأدوات الحالية):**
- الجمل السببية، التنبؤية، الوعود، الأحكام المُضمّنة في نص حر عربي عام. **مفيش خوارزمية regex/pattern-matching بتقدر تغطي البنية اللغوية دي بشكل كامل وحتمي.** الحل المعماري المقترح مش "نتحقق منها بعد ما تتقال" -- هو **نمنع Companionship من إنتاجها من الأساس** بتضييق مدخلاتها (Meaning Packet مالوش بُعد زمني مستقبلي ولا أفعال وعد خالص)، مع فحص heuristic إضافي كطبقة دفاع.

**الأثر على الضمانات النهائية:**
النظام بيضمن حتميًا: **مفيش رقم أو حالة أو استنتاج مش موجود فعليًا في الحقائق المُثبتة هيوصل لأحمد** (ده جوهر المبدأ السابع، ومضمون رياضيًا). النظام **مبيضمنش** حتميًا: إن كل جملة سببية أو تنبؤية ممكنة اتفحصت -- بيضمن بدل كده إنها **ممنوعة تظهر أصلًا** بالتصميم. الفرق بين "اتفحصت ومُرّت" و"اتمنعت من الظهور" هو بالظبط الفرق بين ضمان شكلي وضمان حقيقي -- وده اللي التصميم ده بيختاره عمدًا.
