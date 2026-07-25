# Event Schema & Store — Stage 1
تاريخ: 2026-07-24
الحالة: **منفّذ** (`services/event_store.py`) — لسه مش متربط بأي أداة كتابة حالية.
المرجع السابق: [AUDIT_REPORT_STAGE0.md](AUDIT_REPORT_STAGE0.md)

---

## 1. الفلسفة

القانون الحاكم: **"لا يجوز لآدم أن يعبّر عن حالة داخلية ما لم تكن مبنية على دليل قابل للرصد."**

الحدث (Event) هو أصغر وحدة "دليل" في النظام كله. كل حالة داخلية مستقبلية
(Self-State — مرحلة 5) هترجع لحدث أو أكتر مسجل هنا بالـ `event_id` بتاعه
(`evidence_event_ids` — مرحلة 7)، مش لتخمين أو استنتاج غير موثق.

**ملاحظة تسمية:** فيه كلاس اسمه `BahrEvent` في `executive_brain.py` — ده مفهوم
مختلف تمامًا (رسالة/جدولة داخلة للـ Executive Brain)، مالوش علاقة بالـ Event
Schema ده. الاسمين موجودين في نفس الكودبيز عن قصد بمعنيين مختلفين — منعًا للبس،
أي كود جديد في الـ Observer/Self-State يستخدم "Observed Event" أو "Domain Event"
في التعليقات لو احتاج يميّز بينهم.

---

## 2. الـ Schema

كل حدث = document واحد في مجموعة Firestore `adam_events` (ثابتة في `config.py` كـ
`EVENTS_COLLECTION`)، بالحقول دي:

| الحقل | إجباري؟ | النوع | الوصف |
|---|---|---|---|
| `event_id` | مولّد تلقائيًا | string (uuid4) | معرّف الحدث، هو نفسه doc ID في Firestore |
| `entity.type` | ✅ إجباري | string | نوع الكيان اللي اتغيّر (مثلاً `loan_installment`) |
| `entity.id` | ✅ إجباري | string | معرّف الكيان تحديدًا (identity_key، مثلاً `valu_0`) |
| `attribute` | ✅ إجباري | string | الصفة اللي اتغيّرت تحديدًا (مثلاً `paid_status`) |
| `previous_value` | اختياري | any | القيمة قبل الحدث (`None` لو حدث إنشاء) |
| `new_value` | اختياري | any | القيمة بعد الحدث |
| `source` | اختياري (افتراضي `"unknown"`) | string | مين لاحظ الحدث؟ `"llm_tool"` / `"scheduler"` / `"manual"` ... |
| `actor` | اختياري | string | تحديد أدق للمصدر، مثلاً اسم الأداة `"loan_mark_paid"` أو اسم الـ job |
| `chat_id` | اختياري | int/None | محادثة Telegram اللي الحدث طلع منها (لو موجودة) |
| `raw_context` | اختياري | dict | المدخلات الخام اللي أدت للحدث (evidence إضافي) |
| `metadata` | اختياري | dict | حقل مفتوح للتوسع المستقبلي (مثلاً normalized fields في مرحلة 3) |
| `occurred_at` | مولّد تلقائيًا | string (ISO, توقيت القاهرة) | وقت تسجيل الحدث |
| `entity_key` | مشتق تلقائيًا | string | `"{entity.type}:{entity.id}"` — حقل مساعد للاستعلام السريع بس، مش جزء من العقد الدلالي |

### الحقول الإجبارية (entity + attribute)

الـ API (`record_event`) بيرفض الحفظ بالكامل (بيرمي `InvalidEventError`) لو
`entity_type` أو `entity_id` أو `attribute` فاضيين. مفيش حدث "غامض" ممكن
يتسجل في الـ Store.

---

## 3. الـ API (`services/event_store.py`)

```python
record_event(
    entity_type, entity_id, attribute,   # إجبارية
    new_value=None, previous_value=None,
    source="unknown", actor="", chat_id=None,
    raw_context=None, metadata=None
) -> event_id: str

get_event(event_id) -> dict | None                       # read-only
get_events_for_entity(entity_type, entity_id, limit=200) -> list[dict]   # read-only, مرتّبة زمنيًا
```

**Append-only بالتصميم:** مفيش `update_event` ولا `delete_event` في الـ API خالص.
أي تصحيح لاحق لازم يكون حدث جديد بيشاور على القديم (عبر `metadata` أو
`raw_context`)، مش تعديل فوق السجل الأصلي. ده شرط أساسي عشان الـ Store يفضل
دليل موثوق — لو ينفع يتعدّل، بيبطل يبقى دليل.

---

## 4. مثال تصوّري (توضيحي بس — لسه مش مفعّل)

لما مرحلة 2 (Loan Command API) تتنفذ، `loan_record_installment` هيسجل حدث
شكله كده (تصور، مش كود فعلي حاليًا):

```python
event_store.record_event(
    entity_type="loan_installment",
    entity_id="valu_0",                 # = identity_key
    attribute="paid_status",
    previous_value=False,
    new_value=True,
    source="llm_tool",
    actor="loan_mark_paid",
    chat_id=123456789,
    raw_context={"program_name": "فاليو", "month_key": "01/07/2026", "paid": True},
)
```

`entity_id="valu_0"` هو نفسه الـ identity_key المستخدم فعليًا في `loan_service.py`
الحالي (`f"{program_id}_{index}"`) — يعني التكامل مع مرحلة 3 (Conflict Observer)
هيبقى مباشر، مش محتاج إعادة تصميم.

---

## 5. القرارات اللي اتاخدت وأسبابها

1. **`entity` كـ nested object `{type, id}`** بدل ما يكون حقل واحد نصي —
   عشان يبقى فعلاً "explicit" زي ما اتطلب (نوع + هوية منفصلين وواضحين)، مع
   الاحتفاظ بحقل `entity_key` مشتق للاستعلام السريع في Firestore من غير
   الحاجة لـ composite index (equality على حقل واحد بس).

2. **الملف منفصل (`services/event_store.py`)** مش جزء من `firebase_service.py` —
   لإنه بنية تحتية لمشروع مستقل (Self-State & Observation)، مش "domain" زي
   الأقساط/المصاريف. الفصل ده بيخلي أي مراجعة مستقبلية للـ Observer/Self-State
   تلاقي كل حاجة في مكان واحد واضح.

3. **مفيش ربط بأي أداة كتابة حالية في المرحلة دي.** `loan_mark_paid` وباقي
   الأدوات لسه بتكتب زي ما هي بالظبط (راجع Audit Report). الربط الفعلي
   (منع الكتابة المباشرة، واستبدالها بـ Command API اللي بينده `record_event`)
   هو صلب مرحلة 2، مش مرحلة 1.

---

## 6. التحقق (Verification)

اتعمل تحقق فعلي (مش نظري) عن طريق `test_event_store.py` في جذر المشروع:
- تسجيل حدث حقيقي في Firestore الفعلي (بيئة الإنتاج، لكن في collection جديدة
  تمامًا `adam_events` ماليهاش أي تأثير على أي بيانات موجودة).
- قراءته تاني بـ `get_event` والتأكد إن كل الحقول رجعت زي ما اتسجلت.
- التأكد إن `get_events_for_entity` بيرجع نفس الحدث.
- التأكد إن الحفظ بيترفض فعليًا (`InvalidEventError`) لو `entity_type` أو
  `entity_id` أو `attribute` فاضيين -- 3 حالات اتجربت.
- مسح الحدث التجريبي بعد التأكد (تنظيف، مش جزء من الـ API نفسه — الـ delete
  ده يدوي لمرة واحدة بس عشان الـ Store يفضل نضيف من بيانات اختبار).

نتيجة التشغيل الفعلي موضّحة في رسالة التسليم.

---

## 7. Definition of Done — مرحلة 1 (مقترح للاعتماد)

- [x] Schema صريح موثّق (الملف ده) بحقول `entity` (type+id) و `attribute` إجبارية.
- [x] Event Store API منفّذ (`record_event`, `get_event`, `get_events_for_entity`) و Append-only فعليًا (مفيش update/delete في الـ API).
- [x] الحفظ بيرفض فعليًا أي حدث ناقص الحقول الإجبارية (اتأكد بالتشغيل الفعلي).
- [x] تحقق فعلي (مش نظري) إن الكتابة والقراءة شغالين ضد Firestore الحقيقي.
- [ ] **قرار أحمد:** اعتماد المرحلة كـ "خلصت" والانتقال لمرحلة 2 (Loan Command API).

مفيش أي أداة كتابة حالية اتغيّرت في المرحلة دي -- السلوك الحالي لـ `loan_mark_paid`
وكل الأدوات التانية زي ما هو بالظبط، زي ما هو متفق عليه (مرحلة 1 بنية تحتية بس).
