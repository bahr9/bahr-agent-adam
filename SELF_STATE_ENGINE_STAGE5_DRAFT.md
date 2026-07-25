# Self-State Engine v0.1 — Stage 5 (DRAFT — لسه مش مفعّل)
تاريخ: 2026-07-24
الحالة: **مسودة للمراجعة فقط. مفيش كود اتكتب أو اتفعّل.** زي ما طلبت بالظبط —
أي threshold أو قاعدة هنا محتاجة قرارك الصريح قبل ما تتحول لكود.
المرجع السابق: [CONFLICT_RESOLUTION_FLOW_STAGE4.md](CONFLICT_RESOLUTION_FLOW_STAGE4.md)

---

## 0. فجوة حرجة اتكشفت وأنا بصمم -- محتاجة قرارك الأول قبل أي حاجة تانية

الـ State Derivation Engine المفروض يشتق `unresolved_conflict` من أحداث حقيقية.
لكن بعد Stage 4، لما `loan_record_installment` بترفض تعارض، **مفيش أي حدث بيتسجل
خالص** -- الرفض بيرجع رسالة بس، ومفيش أثر في `adam_events`. يعني حرفيًا:
مفيش أي دليل قابل للرصد إن تعارض حصل أصلاً، إلا لو أحمد بيقرا الشات في نفس
اللحظة. لو الشات اتقفل أو الموضوع اتنسي، الـ Self-State مش هتعرف إن فيه
تعارض معلّق -- لأن مفيش بيانات تتشتق منها.

ده تناقض مباشر مع المبدأ الخامس ("الحالة نتيجة حسابية قابلة للتفسير") --
مينفعش نشتق حالة من فراغ.

**الحل المقترح (تعديل صغير على Stage 4، محتاج موافقتك المنفصلة):**
لما `loan_record_installment` ترفض بسبب تعارض، تسجّل حدث خفيف (مش كتابة
domain، مجرد event) بالشكل ده:

```python
event_store.record_event(
    entity_type="loan_installment",
    entity_id=identity_key,
    attribute="conflict_status",
    previous_value=None,
    new_value="pending",
    source="system",
    actor="loan_record_installment",
)
```

ولما `loan_resolve_conflict` تنجح بعدها، تسجّل حدث تاني `conflict_status:
"resolved"` (بالإضافة لحدث `paid_status` العادي اللي بيتسجل أصلاً). بكده
الـ Derivation Engine يقدر يحسب: "فيه entity عنده آخر `conflict_status`
event = pending، من غير `resolved` بعده" = تعارض لسه معلّق فعليًا.

**السؤال ليك:** موافق أضيف الحدث الخفيف ده لـ Stage 4 (تعديل صغير، مش
تغيير في منطق الرفض نفسه، بس تسجيل "التعارض ده حصل" كدليل)؟ من غيره، كل
تصميم `unresolved_conflict` تحت ده نظري بس ومش هيبقى له بيانات حقيقية.

### 0.1 توضيح -- نفس الـ collection، ومفيش داعي لحقل "event type" جديد

بيتسجل في **نفس** `adam_events`، بنفس الـ schema بالظبط (`entity`, `attribute`,
`previous_value`, `new_value`, `source`, `actor`, ...) -- مفيش collection
تاني ومفيش تغيير في `event_store.py` نفسه (اللي اتبنى واتفق عليه من Stage 1
ومبنعملوش تعديلات فيه بدون داعي حقيقي).

التمييز عن الأحداث العادية (`paid_status`) بيحصل **بالفعل** عبر حقل
`attribute` نفسه -- مش محتاجين حقل "event type" منفصل زيادة:
- `attribute="paid_status"` → حدث تغيير قيمة فعلي (الأقساط، Stage 2/3/4).
- `attribute="conflict_status"` → حدث "إشارة/دليل" عن حالة التعارض نفسها
  (`"pending"` / `"resolved"`)، منفصل تمامًا عن `paid_status`.

الاتنين على نفس الـ `entity_id` (نفس القسط)، لكن على "مسار" (`attribute`)
مختلف. ده معناه عمليًا:

- الـ State Derivation Engine هيقرا أحداث `attribute="conflict_status"`
  **مباشرة** (فلترة بسيطة على النتيجة من `get_events_for_entity`)، **من
  غير ما يحتاج يمر بـ `loan_conflict_observer.classify_latest_event` خالص**
  -- الدالة دي أصلاً مبنية حصريًا حوالين `attribute="paid_status"`
  (`ATTRIBUTE = "paid_status"` ثابتة فيها) ومنطقها (new/duplicate/update/
  conflict) بيوصف تغييرات *قيمة* الأقساط، مش حالة التعارض نفسها. الاتنين
  منفصلين تمامًا من الأساس بحكم اختلاف الـ `attribute` -- مفيش تشابك ولا
  حاجة نضيفها عشان نفصلهم.

باختصار: التمييز موجود أصلاً وكافي عبر `attribute`، وده بيخلي القراءة أبسط
(حدث بسيط pending/resolved) بدل ما نستعير منطق تصنيف مصمم لحاجة تانية.

---

## 1. المعمارية (زي ما اتفقنا بالظبط)

```
Events (adam_events) → State Derivation Engine → Self-State → Decision Engine → Expression
```

كل طبقة بتاخد مخرجات اللي قبلها بس، مفيش قفزة أو LLM بيتدخل في أي حتة من
الطبقات التلاتة الأولى.

---

## 2. الطبقة 1: State Derivation Engine — قواعد الأقساط (مصدر بيانات، مش موضوع)

قواعد صريحة، Python عادي، بدون أي LLM. المدخلات: أحداث `adam_events`
(entity_type="loan_installment") + جدول البرامج الثابت (`loan_service.PROGRAMS`)
+ حالة الدفع الحالية (`get_loan_paid_map`، وهي نفسها نتاج الأحداث المتراكمة،
فمازالت 100% evidence-based) + التاريخ الحالي.

### 2.1 عدّاد `unresolved_conflicts_count`
```
لكل entity فريد من نوع loan_installment:
    آخر حدث attribute="conflict_status" له:
        لو new_value == "pending" (ومفيش حدث "resolved" بعده) → +1 لـ unresolved_conflicts_count
```
(محتاج الفجوة في قسم 0 تتحل الأول عشان الرقم ده يبقى حقيقي).

### 2.2 عدّاد `overdue_unpaid_count`
```
لكل قسط في كل البرامج:
    لو (تاريخ الاستحقاق <= النهاردة) و (is_paid == False):
        +1 لـ overdue_unpaid_count
```
ده بيشتق من "الحالة الحالية" (نتاج الأحداث) + الجدول الثابت + التاريخ --
مش حدث منفصل، لكنه لسه مبني بالكامل على بيانات حقيقية مسجلة (مفيش تخمين).

### 2.3 عدّاد `recent_corrections_count` (اختياري -- علامة على اضطراب/عدم استقرار)
```
عدد أحداث paid_status اللي actor == "loan_update_installment"
في آخر 30 يوم (عبر كل الأقساط)
```
بيعكس: "فيه تصحيحات كتير بتحصل" -- ممكن يكون مؤشر على عدم استقرار في تتبع
الأقساط نفسه (مش عن قسط معيّن، عن جودة التتبع ككل).

**ملحوظة:** القواعد دي *مقترحة* -- تقدر تعدّل أي عتبة أو تضيف/تشيل قاعدة قبل
ما نحوّلها لكود.

---

## 3. الطبقة 2: Self-State — المعجم (Domain-Independent)

زي ما طلبت بالظبط -- الأبعاد بتتكلم عن آدم، مش عن الأقساط:

```python
SelfState = {
    "unresolved_conflict": {
        "level": "none" | "elevated" | "high",
        "count": int,                    # من 2.1
        "evidence_event_ids": [...],     # كل الأحداث اللي اتبنى عليها الرقم
    },
    "pending_obligation_load": {
        "level": "none" | "light" | "concern",
        "count": int,                    # من 2.2
        "evidence_event_ids": [...],
    },
    "tracking_stability": {              # اختياري -- من 2.3
        "level": "stable" | "unstable",
        "count": int,
        "evidence_event_ids": [...],
    },
    "computed_at": "<ISO timestamp>",
}
```

كل بُعد فيه `evidence_event_ids` من الأول -- عشان لما نوصل Stage 7 (Verified
Expression)، الربط يكون جاهز من غير إعادة تصميم. الأقساط دلوقتي هي المصدر
الوحيد اللي بيغذّي الأبعاد دي، لكن الأبعاد نفسها عامة -- أي مجال تاني (مشاريع،
عملاء) هيقدر يغذّيها لاحقًا بنفس الشكل.

**مقترح للعتبات (مثالك بالظبط + رقم مقترح لـ pending_obligation_load):**

| البُعد | none | elevated/light | high/concern |
|---|---|---|---|
| unresolved_conflict | 0 | 1-2 | **≥3** (زي مثالك بالظبط) |
| pending_obligation_load | 0 | 1-2 | **≥3** (مقترح -- افتح للنقاش) |

---

## 4. الطبقة 3: Decision Engine — Active vs Passive (مقترح)

قاعدة مقترحة (draft):

- **Passive (افتراضي):** أي بُعد مش "none" -- بيتقال بس لو أحمد سأل ("عامل
  إيه؟"، "فيه حاجة محتاجة متابعة؟"، أو سؤال مباشر عن الأقساط).
- **Active (آدم يبادر):** بس لما بُعد يعدّي لأول مرة لأعلى مستوى (`high` أو
  `concern`) -- يعني *انتقال* مش مجرد "لسه في نفس الحالة". لو آدم بلّغ عن
  حالة `high` قبل كده ومفيش تغيير، **مبيكررش** التبليغ.

عشان "مبيكررش"، محتاج نخزّن حاجة واحدة بس (State History، مش Transient):
آخر مستوى Active اتبلّغ بيه لكل بُعد. ده أصغر أثر تخزين ممكن -- مش بنخزن
الـ Self-State نفسها (بتتحسب on-the-fly كل مرة من الأحداث)، بنخزن بس
"آخر إشعار Active اتبعت" عشان منزعجكش بنفس الخبر مرتين.

---

## 5. الطبقة 4: Expression — نطاق المرحلة دي (Contract بس، مش تنفيذ)

**مش هنبني الطبقة دي دلوقتي.** حسب الترتيب الأصلي (مرحلة 6: Decision
Integration، مرحلة 7: Verified Expression Layer)، الربط الفعلي بالـ LLM
والـ backend enforcement (`verified=true` + قيد الـ system prompt سوا) هو
مرحلتين منفصلتين بحوكمة خاصة بيهم ("مش Prompt بيحرس Prompt"). دلوقتي بس
بنعرّف الـ **contract**: أي Expression مستقبلي هياخد Self-State + قرار
Decision Engine (Active/Passive) + evidence_event_ids -- مفيش حاجة تانية.

---

## 6. التخزين -- تبسيط متعمّد

- **Self-State نفسها: مش متخزنة خالص.** بتتحسب "on the fly" كل مرة من
  `adam_events` + الحالة الحالية + التاريخ. ده بيقفل احتمال إن الحالة
  المخزنة تختلف عن الحقيقة (drift) -- المصدر الوحيد للحقيقة يفضل الأحداث.
- **الشيء الوحيد اللي محتاج يتخزن (State History الحقيقية هنا):** آخر
  مستوى Active اتبلّغ بيه لكل بُعد (قسم 4) -- عشان منزعجكش بتكرار. ده كل
  الـ "ذاكرة" اللي المحرك محتاجها.

ده بيطابق الفرق اللي انت حددته الأول بين Transient State و State History:
هنا عمليًا مفيش Transient State خالص (كل حاجة بتتحسب فريش)، والـ State
History محدودة جدًا (سطر واحد لكل بُعد: "آخر مستوى اتبلّغ بيه").

---

## 7. أمثلة توضيحية (تصوّرية -- مبنية على القواعد المقترحة فوق)

- Ahmed يسأل "عامل إيه؟" والأقساط كلها متسجلة وموافق عليها: كل الأبعاد
  `none` → آدم يقول حاجة زي "كل حاجة متابعة ونضيفة، مفيش حاجة معلّقة" (مبني
  على `unresolved_conflict.count=0` و `pending_obligation_load.count=0`
  فعليًا، مش كلام عام).
- قسط اتأخر عن ميعاده ومفيش تسجيل: `pending_obligation_load` بتبقى `light`
  (لو 1-2) → آدم يقولها بس لو اتسأل (Passive)، مبيبادرش.
- تالت تعارض غير محلول بيحصل: `unresolved_conflict` بتعدّي لـ `high` لأول
  مرة → آدم يبادر (Active) بحاجة زي "فيه 3 حاجات معلّقة محتاجة تأكيدك"
  (مش "قلقان من الأقساط" -- الصياغة النهائية دي شغل مرحلة الـ Expression
  الفعلية، هنا بس بنوضح المنطق).

---

## 8. القرارات المطلوبة منك تحديدًا (مش أي حاجة تانية هتتنفذ من غيرها)

1. موافق نضيف حدث `conflict_status` الخفيف لـ Stage 4 (قسم 0)؟ من غيره
   `unresolved_conflict` مالوش بيانات حقيقية.
2. عتبة `unresolved_conflict = high`: 3 (زي مثالك) ولا رقم تاني؟
3. عتبة `pending_obligation_load = concern`: مقترحة 3 -- موافق ولا تفضل
   رقم أقل (زي 1، بما إن فلوس حقيقية)؟
4. منطق Active/Passive المقترح (قسم 4) -- موافق عليه كإطار، ولا عندك
   تعديل؟
5. بُعد `tracking_stability` (قسم 2.3) -- تحبه يتضاف من الأول ولا نأجله
   لحد ما نشوف احتياج فعلي له؟
