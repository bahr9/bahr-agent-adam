# خطة الـ Schema للهجرة من Firestore لـ Supabase

**تاريخ:** 2026-08-05 · **الحالة:** 🟡 للمراجعة — مفيش أي كود هجرة اتكتب لسه

مستخرجة من **الكود بس** (Firestore كوتاه خلصانة، فمفيش أي قراءة من البيانات
الحية). كل حاجة مش متأكد منها مكتوبة صراحة كسؤال مش كافتراض.

---

## 1. تصحيح لازم يتقال الأول: العدد مش 26

أنا قلتلك ٢٦ collection من `config.py`. الرقم الصح **٣٠**، لأن أربعة متعرّفين
جوه `firebase_service.py` مش في `config.py`:

| Collection | مكان التعريف | الحالة |
|---|---|---|
| `recurring_reminders` | `firebase_service.py:989` | حية — ودي اللي متهاجرة جزئيًا بالفعل |
| `memory_notes` | `firebase_service.py:1066` | حية — **أكبر مجموعة حجمًا** |
| `bahrSites` | `firebase_service.py:812` | حية |
| `depaProjects` | `firebase_service.py:813` | **ميتة** — الثابت مش متنادى ولا مرة |

أي خطة اتبنت على `config.py` لوحده كانت هتفقد `memory_notes` — وهي أكبر
مجموعة عندنا (١٧٠ مستند وقت آخر قياس). ده كان هيبان بعد الهجرة مش قبلها.

---

## 2. أول قرار: إيه اللي بيتهاجر أصلاً

مش كل الـ ٣٠ يستاهلوا. التصنيف ده محتاج موافقتك:

### أ) ميتة — مفيش أي كود بيقراها أو يكتبها (٥)

| Collection | الدليل | الاقتراح |
|---|---|---|
| `recurring_tasks` | ثابت بس، صفر استخدام | **متتهاجرش** |
| `depaProjects` | ثابت بس، صفر استخدام | **متتهاجرش** |
| `clients` | دوال موجودة، **صفر مستدعين** — اتحلّت محلها `client_followups` | صدّرها للأرشيف بس |
| `office_tasks` | دوال موجودة، صفر مستدعين | صدّرها للأرشيف بس |
| `site_projects` | دوال موجودة، صفر مستدعين | صدّرها للأرشيف بس |

التلاتة الأخيرة **في ليستة النسخ الاحتياطي**، يعني ممكن يكون فيها بيانات
قديمة. اقتراحي: تتصدّر في النسخة الكاملة، بس مايتعملهاش جداول في Supabase.

### ب) بتتكتب ومحدش بيقراها في الإنتاج (٢)

`adam_state_snapshots` و `adam_expressions` — دول أثر تدقيق (Stage 6/7).
بيتكتبوا فعلاً، بس **مفيش أي كود إنتاج بيقراهم** — الاختبارات بس.

**سؤال ليك:** نهاجرهم ونكمّل تسجيل، ولا نوقف الكتابة ونكتفي بالأرشيف؟

### ج) مملوكة لبرّه — أخطر بند في الخطة كلها (١)

`projects` — دي مجموعة **فرونت Bahr OS**، وآدم بيقرا **ويكتب** فيها.

الحقول `items` و `deductionRates` و `finaldata` بيقراها آدم و**عمره ما كتبها**
— يعني الفرونت هو اللي بيكتبها، وشكلها الداخلي مش معروف من الكود ده خالص.

**دي مش قرار تقني، دي قرار تنسيق.** المجموعة دي مينفعش تتحرك من غير ما
فرونت Bahr OS يتحرك معاها. الاختيارات:

1. تفضل على Firestore والباقي يهاجر (نظام مختلط)
2. تتهاجر مع تعديل الفرونت — محتاج وصول لسورس الفرونت
3. تتأجل لمرحلة تانية

**محتاج قرارك هنا قبل أي حاجة تانية.** و`bahrSites` عليها نفس الشك.

### د) تتهاجر (٢٢) — دي صلب الخطة

---

## 3. تاني قرار: الوقت — وده أكبر مكسب صحة في الهجرة كلها

فيه **خمس صيغ مختلفة** لتخزين الوقت في نفس قاعدة البيانات:

| # | الصيغة | مثال | المصدر |
|---|---|---|---|
| **A** | epoch بالميلي، رقم | `1785490887553` | `int(time.time()*1000)` |
| **B** | ISO بإزاحة القاهرة | `2026-08-05T14:23:11+03:00` | `now_cairo().isoformat()` |
| **C** | زي B بس بمسافة مش `T` | `2026-08-05 14:23:11+03:00` | `str(now_cairo())` |
| **D** | نص ساذج بالدقيقة | `2026-08-05 14:23` | `datetime.now().strftime(...)` |
| **E** | نص ساذج بالميكروثانية | `2026-08-05 14:23:11.123456` | `str(datetime.now())` |

**الخبر الكويس:** مفيش ولا `Timestamp` object بتاع Firestore في المشروع كله.
كل الأوقات إما رقم بايثون أو نص بايثون — يعني الهجرة تحويل نصي بحت، مفيش
أنواع Firestore هتعقّدنا.

### 🔴 الخبر الوحش: صيغتين D و E بيستخدموا `datetime.now()` مش `now_cairo()`

يعني بيسجلوا توقيت **السيرفر** — واللي على Railway هو **UTC**. النتيجة إن
`expenses.date` غالبًا **متأخر ٢–٣ ساعات** عن كل تاريخ تاني في النظام، ومفيش
في البيانات نفسها أي حاجة تقولك كده.

والحقول المتأثرة:

| الحقل | الاستخدام الحرج |
|---|---|
| `expenses.date` | تنبيه المصاريف الشهري بيقارن `date.startswith("YYYY-MM")` |
| `decision_ledger.date` | عرض القرارات |
| `memory_notes.timestamp_str` | `get_mood_history` بيقارنه نصيًا |

**سؤال ليك:** المصاريف اللي اتسجلت بين ٢١:٠٠ و٢٣:٥٩ بتوقيت القاهرة اتسجلت
على اليوم اللي فات. نصحّح ده أثناء الهجرة (نضيف ٢–٣ ساعات حسب التوقيت
الصيفي)، ولا نسيبه زي ما هو ونوثّقه؟

رأيي: **نصحّحه**. دي فرصة مش هتتكرر، والبيانات لسه صغيرة.

### القرار المعتمد

**كل عمود وقت في Postgres يبقى `timestamptz`.** ودي مكاسب فورية:

- `event_store.py:238` بيعيد الترتيب في بايثون بعد كل استعلام — **يتشال**
- `tool_health_engine` فيه هامش ٣ ساعات عشان الإزاحة بتتغير مع التوقيت الصيفي — **يتشال**
- كل مقارنات المدى دلوقتي **نصية** (lexicographic) وغلط على حدود التوقيت الصيفي — **تتصلح**

والتواريخ اللي مش لحظات زمنية تفضل `date`:
`client_followups.next_followup_date`، والـ deadline المستخرج من `memory_notes`،
و`date` بتاع أقساط القروض (`DD/MM/YYYY`).

---

## 4. النمط الموحّد لكل جدول

كل جدول جديد بياخد نفس الهيكل — وده اللي طلبته:

```sql
create table public.<name> (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,          -- عمود الجسر: بيربط الصف بالمستند الأصلي
    ...                                 -- أعمدة الدومين
    created_at    timestamptz not null default now(),
    updated_at    timestamptz
);
create index on public.<name> (firestore_id);
```

`firestore_id` هو اللي بيخلي الـ dual-write يعرف يحدّث الصف الصح، وبيخلي
التحقق بعد الهجرة ممكن (نقارن عدد ومحتوى الصفوف بالمستندات).

---

## 5. الجداول — التصميم المقترح

### 5.1 `adam_events` — أهم جدول عندنا

٤٣٧٨ مستند، وسجل الأحداث اللي نظام Self-State كله قايم عليه.

```sql
create table public.adam_events (
    id                uuid primary key default gen_random_uuid(),
    firestore_id      text unique,               -- == event_id القديم
    event_id          uuid not null unique,
    entity_type       text not null,
    entity_id         text not null,
    attribute         text not null,
    previous_value    jsonb,                     -- متعدد الأنواع بالتصميم
    new_value         jsonb,
    source            text not null default 'unknown',
    actor             text not null default '',
    chat_id           text,                      -- int أو str في الأصل
    raw_context       jsonb not null default '{}',
    metadata          jsonb not null default '{}',
    occurred_at       timestamptz not null
);

create index on public.adam_events (entity_type, entity_id, occurred_at desc);
create index on public.adam_events (entity_type, attribute, occurred_at desc);
```

**اللي بيتشال:** `entity_key` و `type_attribute_key`. دول أعمدة مشتقة
اتعملت **بس** عشان قيود فهرسة Firestore. في Postgres الفهرس المركّب بيغني
عنهم تمامًا.

**اللي بيتكسب:** الاستعلامين اللي محتاجين composite index في Firestore
(ولسه **ناقصين في الإنتاج من ٢١ يوليو**) بيشتغلوا فورًا وصح.

⚠️ **نتيجة مهمة:** بما إن الفهارس دي ناقصة حاليًا، الاستعلامات في الإنتاج
بترجع **عيّنة عشوائية** مرتبة بالـ UUID. يعني أي حاجة آدم قالها بناء على
"آخر حدث" في الفترة دي مش مضمونة.

### 5.2 `memory_notes` — أكبر مجموعة، وأسوأ schema

المشكلة الجوهرية: **المواعيد النهائية متخزنة جوه النص**.

الكتابة: `f"{text} [Deadline: {deadline_date}]"`
القراءة: `re.search(r'Deadline: (\d{4}-\d{2}-\d{2})', text)`

مفيش عمود للـ deadline خالص. ده أهم تطبيع في الهجرة كلها.

```sql
create table public.memory_notes (
    id             uuid primary key default gen_random_uuid(),
    firestore_id   text unique,
    user_id        text not null,
    text           text not null,          -- بعد شيل الـ [Deadline: ...]
    deadline       date,                   -- ← عمود حقيقي بدل regex
    category       text not null default '',
    related_to     text not null default '',
    status         text not null default 'active',   -- الغياب كان معناه active
    urgent_alert_sent boolean not null default false,
    created_at     timestamptz not null,
    updated_at     timestamptz
);

create index on public.memory_notes (user_id, created_at desc);
create index on public.memory_notes (deadline) where deadline is not null;
```

`timestamp_str` **بيتشال** — هو نسخة تانية زايدة من نفس اللحظة، وبتختلف عن
`created_at` لأنها بتوقيت السيرفر.

### 5.3 `conversations` — من مصفوفة متداخلة لجدول ابن

دلوقتي: مستند واحد لكل مستخدم فيه `messages: list[dict]`، وبيتقصّ لـ ١٠٠ لما
يوصل ٢٠٠ (إعادة كتابة المصفوفة كلها).

```sql
create table public.conversation_messages (
    id             bigint generated always as identity primary key,
    user_id        text not null,
    user_text      text not null,
    assistant_text text not null,
    occurred_at    timestamptz not null
);
create index on public.conversation_messages (user_id, occurred_at desc);
```

القص من ٢٠٠ لـ ١٠٠ بيبقى **سياسة احتفاظ** (حذف بشرط) مش إعادة كتابة عند كل
رسالة. وده بيشيل سباق `ArrayUnion` اللي الأوديت رصده.

### 5.4 `loans` — من خريطة في مستند لجدول

دلوقتي: مستند واحد `paid_status` فيه `paid: {"valu_0": true, ...}`.

```sql
create table public.loan_installment_status (
    identity_key  text primary key,       -- "{program_id}_{index}"
    program_id    text not null,
    installment_index int not null,
    paid          boolean not null,
    updated_at    timestamptz not null default now()
);
```

الكتابة الذرية (حدث + دفع) اللي دلوقتي `Firestore batch` بتبقى **transaction**
عادية — أبسط وأقوى.

⚠️ **لازم يتحافظ عليه:** `get_loan_paid_map` بيفرّق بين تلات حالات —
dict عند النجاح، `{}` لو المستند مش موجود، **`None` عند فشل القراءة**.
التفرقة دي اتعملت في أوديت النهاردة وهي اللي بتمنع الملخص إنه يقول "صفر مدفوع"
أثناء عطل.

### 5.5 `project_files` — الحقائق المتداخلة

دلوقتي: `facts: {category: {key: {value, source, updated_at, computed_area_m2?}}}`

```sql
create table public.project_files (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    display_name  text not null,
    created_at    timestamptz not null,
    updated_at    timestamptz
);

create table public.project_file_facts (
    id               bigint generated always as identity primary key,
    project_file_id  uuid not null references public.project_files(id) on delete cascade,
    category         text not null,      -- فراغات/أبعاد/قرارات/ميزانية/عميل/ملاحظات
    key              text not null,
    value            text not null,
    source           text not null default 'ahmed',
    computed_area_m2 double precision,   -- NULL = مش محسوبة (مش صفر)
    updated_at       timestamptz not null,
    unique (project_file_id, category, key)
);
```

الفئات مجموعة مقفولة، فجدول ابن أحسن من `jsonb`. و`computed_area_m2` لازم
تفضل nullable — الكود بيفرّق صراحة بين "مش محسوبة" و"صفر".

### 5.6 `system_flags` — تلات حاجات مختلفة في مجموعة واحدة

المجموعة دي فيها تلات أشكال مستندات مالهمش أي علاقة ببعض، متفرقين بالـ ID بس.
لازم تتفكّ لتلاتة:

| المستند الحالي | الجدول المقترح |
|---|---|
| `chat_id` | صف في جدول إعدادات (`app_settings`) |
| `monthly_alert_{YYYY-MM}` | `monthly_alerts_sent(month date primary key, total numeric, sent_at timestamptz)` |
| `learning_fallback` | عدّاد في `app_settings` أو جدول عدّادات |

مستندات `monthly_alert_*` بتزيد للأبد وبتخزن البيانات **في المعرّف نفسه** —
نمط غلط بيتصلح هنا مجانًا.

### 5.7 الباقي — جداول مباشرة

`reminders`, `expenses`, `decision_ledger`, `personal_tasks`, `ideas`,
`ain_al_khabeer_logs`, `agent_tasks`, `price_base`, `bahr_graph_nodes`,
`client_followups`, `user_memory`, `adam_human_model`,
`tool_health_checks`, `tool_failures_log`, `tool_health_alert_state`,
`project_status_alert_state`, `adam_self_state`, `eye_expert_config`.

تفاصيلها في الجرد الكامل — تصميمها مباشر ومفيش فيها مفاجآت هيكلية.

---

## 6. مخاطر الأنواع — لازم تتحسم قبل الجداول تتعمل

| # | المشكلة | القرار المطلوب |
|---|---|---|
| 1 | `reminders.user_id` مرة `int` ومرة `str` في نفس العمود | نوحّده `text`؟ |
| 2 | `price_base.price` **رقم متخزن كنص** | نحوّله `numeric`؟ (لازم نتحقق من كل القيم الأول) |
| 3 | `projects.area` ممكن `float` أو `int` أو `""` | يعتمد على قرار البند 2-ج |
| 4 | `projects` فيها **حقلين "آخر تعديل"**: `updatedAt` و `last_updated` | ندمجهم في واحد |
| 5 | `expenses.project` = `None` بينما `decision_ledger.project` = `""` | نوحّد على `NULL` |
| 6 | أسماء حقول عربية: `نص` و `تم` في `personal_tasks` و `ideas` | نعيد تسميتهم (`text`, `done`) مع خريطة تحويل |
| 7 | `adam_human_model` مفاتيحه **مفتوحة** — `update_human_model(key, value)` بيقبل أي مفتاح | `jsonb` بدل أعمدة ثابتة |

---

## 7. حاجات مش قادر أحسمها من الكود

دي محتاجة **نظرة على مستند حي واحد** — والنسخة الاحتياطية على GitHub هي
الطريقة الآمنة (مش بتستهلك كوتا Firestore خالص):

1. شكل `projects.items[]` و `deductionRates` و `finaldata` من جوه
2. هل `bahrSites.client` و `.area` موجودين فعلاً؟ (الكود بيقراهم وعمره ما كتبهم — ممكن باگ)
3. الحقول الفعلية في `clients` و `office_tasks` و `site_projects`
4. كل المفاتيح المستخدمة فعليًا في `adam_human_model`
5. أشكال الـ IDs القديمة في `bahr_graph_nodes` و `client_followups`
   (فيه مستند شبح معروف اسمه `محمد علي` بدل `CLT-XXXX`)

---

## 8. الترتيب المقترح للتنفيذ

| # | الخطوة | الحالة |
|---|---|---|
| 0 | إصلاح نزيف الكوتا | ✅ اتعمل ومنشور |
| 1 | تحويل `recurring_reminders` لـ `timestamptz` | 🟡 SQL جاهز في `migrations/001` |
| 2 | **تصدير كامل للـ ٣٠ collection** | ⏸️ مستني كوتا بكرة |
| 3 | فحص النسخة للإجابة على البند 7 | بعد 2 |
| 4 | مراجعتك للخطة دي + القرارات المعلّقة | ⏳ **دلوقتي** |
| 5 | إنشاء الجداول (SQL) | بعد 4 |
| 6 | dual-write مجموعة بمجموعة، بنفس نمط `recurring_reminders` | بعد 5 |
| 7 | تحويل القراءة لـ Supabase مع fallback | بعد 6 |
| 8 | شيل Firestore بعد فترة استقرار | آخر حاجة |

**قاعدة صارمة للخطوة 6:** مجموعة واحدة في المرة، ومفيش مجموعة تانية تبدأ
قبل ما اللي قبلها تعدّي فترة استقرار. `recurring_reminders` هي النموذج —
الكود بتاعها في `services/recurring_reminders_service.py` وهو المرجع.

---

## 9. القرارات اللي مستنيها منك

1. **`projects` و `bahrSites`** — الفرونت بتاع Bahr OS بيكتب فيهم. نأجلهم؟ نعمل نظام مختلط؟
2. **`adam_state_snapshots` و `adam_expressions`** — محدش بيقراهم. نهاجرهم ولا نأرشفهم؟
3. **الخمس مجموعات الميتة** — أرشيف بس، ولا جداول برضه؟
4. **انحراف `expenses.date`** — نصحّح الـ ٢–٣ ساعات أثناء الهجرة ولا نسيبه موثّق؟
5. **`price_base.price`** — نحوّله رقم ولا نسيبه نص؟

ومفيش أي سطر كود هجرة هيتكتب قبل ما ترد على دول.
