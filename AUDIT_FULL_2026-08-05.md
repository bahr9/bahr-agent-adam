# أوديت شامل لـ ADAM — 2026-08-05

منهج الفحص: 5 وكلاء قروا الكود كله ملف ملف (~340KB كود بايثون)، بالإضافة لتحقق يدوي
من أخطر النقط + تشغيل فعلي للكود لإثبات بعضها + تحليل `bahr_agent.log`.

الحالة العامة: **الكود مش بيقع — بس ده بالظبط المشكلة.** النمط الغالب في المشروع كله هو
`except: pass` و `return []` عند الفشل، يعني الأعطال بتتحول لإجابات غلط بثقة بدل ما تبان كأخطاء.

---

## ✅ اتصلح في نفس اليوم (2026-08-05)

| البند | الملف | التحقق |
|-------|-------|--------|
| 1.1 مطابقة برامج القروض | `loan_service.py` | 21/21 حالة + `test_loan_commands.py` عدّى |
| 1.2 متابعات العملاء (naive/aware) | `claude_service.py` | `test_followups_window.py` 8/8 |
| 2.1 + 2.2 التذكيرات اليومية والتوقيت الصيفي | `main.py`, `recurring_reminders_service.py` | `test_recurring_due.py` 15/15 |
| 3.1 حارس حذف المشاريع | `firebase_service.py` | اتجرب على الإنتاج: رفض معرّف غلط، صفر مشاريع اتلمست |
| 0.2 + 6.5 تغطية الـ backup وفشله الصامت | `backup_service.py` | 5 ← 23 collection، وفشل القراءة بقى مانع للرفع |
| 6.3 سجل واحد باظ بيوقف كل التذكيرات | `main.py` | محاكاة كاملة للـ job |
| 5.4 ملفات وقت التشغيل في git | `.gitignore` | ~1MB اتشال من التتبع |
| 4.2 تقطيع الرسايل عند 4096 | `bot.py` | `test_message_split.py` 13/13 |
| 4.1 `pause_turn` و `max_tokens` و `refusal` | `claude_service.py` | `test_stop_reason.py` 9/9 |
| 4.3 فرض `tool_choice` على `web_search` | `claude_service.py` | أدوات السيرفر مستثناة من الفرض |
| 6.1 تنبيه بيضيع لو الإرسال فشل | `project_status_alerts.py`, `tool_health_alerts.py` | مفيش كتابة حالة عند الفشل |
| 1.3 ملخص القروض بيقول صفر مدفوع عند العطل | `firebase_service.py`, `loan_service.py` | `test_loan_safety.py` 11/11 |
| 1.5 المتأخرات بتشوف شهر واحد بس | `loan_service.py` | بقت بتغطي كل الشهور الفايتة |
| 1.6 `limit` من غير `order_by` | `event_store.py` | استعلام مرتّب + fallback آمن |

**الإجمالي: 180/180 اختبار عدّى** (منهم 56 اختبار جديد اتكتبوا كحُرّاس للباجات دي).

**لسه محتاج تدخّل منك (مفاتيح ووصول مش عندي):**
- بند 0.1 — `GITHUB_TOKEN` و `GITHUB_REPO` في `.env` (من غيرهم مفيش backup هيترفع)
- بند 0.3 — `AGENT_TASKS_SECRET` و `EYE_EXPERT_SECRET`
- بند 0.4 + 1.6 — إنشاء 3 composite indexes، اللينكات جاهزة في
  [`FIRESTORE_INDEXES_REQUIRED.md`](FIRESTORE_INDEXES_REQUIRED.md)

**اكتشاف جديد أثناء الإصلاح (مش في التقرير الأصلي):** 5 أدوات موجودة في `TOOLS`
ومش متصنّفة في `_TOOL_METADATA` بتاع `capabilities_registry` — `generate_mood_board`,
`get_prices`, `get_project_file`, `save_price`, `save_project_fact`. كلهم اتضافوا
2026-08-04. بياخدوا تصنيف افتراضي محافظ فمش عطل، بس `test_tool_health.py` بيفشل
عليهم وبيستاهلوا مراجعة.

---

## 0) حاجات ميتة دلوقتي في الإنتاج (إعدادات ناقصة)

### 0.1 🔴 النسخ الاحتياطي مش شغال من أساسه
- `services/backup_service.py:28-29,83-85`
- `GITHUB_TOKEN` و `GITHUB_REPO` **مش موجودين في `.env`** (اللي فيه 6 متغيرات بس:
  TELEGRAM_TOKEN, ANTHROPIC_API_KEY, FIREBASE_CREDENTIALS_JSON, OPENAI_API_KEY,
  SUPABASE_URL, SUPABASE_KEY).
- النتيجة: `upload_to_github` بيرجع `False` فورًا. الـ job متسجل كل يوم 2:00 ص
  (`main.py:874`) — وبيفشل كل مرة. مفيش أي سطر "Backup" في اللوج كله من 21 يوليو لـ 4 أغسطس.
- **مفيش نسخة احتياطية واحدة موجودة.**

### 0.2 🔴 الـ backup — حتى لو اشتغل — مش بيغطي البيانات المهمة
- `services/backup_service.py:33-39`
- بياخد: `user_memory`, `memory_notes`, `conversations`, `adam_human_model`, `bahr_graph_nodes`
- **مش بياخد**: `expenses`, `loans/paid_status`, `projects`, `adam_events` (سجل الأحداث
  اللي كل نظام Self-State قايم عليه)، `reminders`, `recurring_reminders`, `clients`, `office_tasks`
- يعني كل البيانات المالية بالظبط خارج الحماية.

### 0.3 🔴 endpoint مفيش حد بيقدر يوصله
- `main.py:747,787,811` — `EYE_EXPERT_SECRET` و `AGENT_TASKS_SECRET` مش في `.env`
- الحارس fail-closed (وده صح) → بيرجع 503 لكل طلب. في اللوج بيتكرر لحد 4 أغسطس.
- النتيجة: تسجيل "عين الخبير" من Make.com واقف، ونظام agent-tasks كله واقف
  (التاسكات بتفضل `pending` للأبد).

### 0.4 🔴 Firestore composite index ناقص
- من اللوج (21 يوليو، متكرر): `400 The query requires an index` على `memory_notes`
  (`user_id` + `createdAt`)
- النتيجة: `search_memory_notes` و `list_memory_notes` بيفشلوا. اللينك الجاهز للإنشاء موجود في اللوج.

### 0.5 🟠 تناقض Procfile مع Flask
- `Procfile:1` = `worker: python main.py` ، و `main.py:841` = `flask_app.run(port=8080)` ثابت
- على Heroku الراوتر بيوجّه للـ `web` process اللي رابط `$PORT` بس — يعني الـ worker
  عمره ما هيستقبل HTTP. لو منشور على VM، فالـ Werkzeug dev server بيخدم الإنترنت مباشرة
  (مش production-grade). و `gunicorn` في requirements ومش مستخدم.

---

## 1) بيانات مالية غلط (الأخطر على الشغل)

### 1.1 🔴 القسط ممكن يتسجل على قرض تاني خالص — **مُثبتة بتشغيل الكود**
- `services/loan_service.py:96` — `p["id"].lower() in search`
- الـ id `"ca"` (Credit Agricole) بيماتش أي نص فيه الحرفين دول، و`ca` بيجي قبل `premium` في الليستة.

نتيجة تشغيل فعلي:
```
'premium card' -> ca
'card'         -> ca
'halan card'   -> ca
```
- **السيناريو**: تقول "دفعت بريميم كارد" → النظام يسجل قسط **Credit Agricole بـ 13,000 جنيه**.
  وحارس التعارض (Stage-4) مش بيمسكها لأن أول كتابة مالهاش أحداث سابقة.

### 1.2 🔴 متابعات العملاء بترجع "مفيش" **دايمًا** — **مؤكدة**
- `services/claude_service.py:1573-1576`
- `datetime.fromisoformat(nfd)` بيطلع naive (التواريخ متخزنة `YYYY-MM-DD`)، و`now_cairo()`
  بيطلع aware (`ZoneInfo("Africa/Cairo")` — `utils/time_utils.py:19-23`).
- `(followup_date - now)` بيرمي `TypeError` → و`except: pass` في سطر 1576 بيبلعه لكل سجل.
- **السيناريو**: عندك 5 عملاء محتاجين متابعة الأسبوع ده، تسأل "مين محتاج متابعة؟"،
  الرد: "مفيش متابعات خلال 3 أيام". غلط بثقة، ومفيش أي خطأ في اللوج. من يوم ما اتكتبت.

### 1.3 🟠 ملخص القروض بيقول كل الأقساط مدفوعة صفر عند أي عطل قراءة
- `services/firebase_service.py:709-711` — `get_loan_paid_map` بيرجع `{}` عند أي exception
- `get_overview` (`loan_service.py:151-179`) بيحسب paid=0 لكل برنامج ويعرضها كحقيقة.
- **السيناريو**: انقطاع لحظي في Firestore وأنت بتسأل عن الملخص → يقولك إنك مدين
  بالإجمالي كامل شامل شهور دفعتها بالفعل، من غير أي إشارة لخطأ.

### 1.4 🟠 حارس التعارض بيفتح عند الخطأ (fail-open)
- `services/event_store.py:227-229` بيرجع `[]` عند أي exception؛
  `services/loan_commands.py:126-131` بيفسر الليستة الفاضية كـ "مفيش أحداث سابقة" ويكمّل الكتابة.
- **السيناريو**: خطأ لحظي أثناء تسجيل قسط بيناقض سجل موجود → الحارس والـ observer
  والـ conflict event كلهم بيتخطوا بصمت.

### 1.5 🟠 المتأخرات بتشوف شهر واحد بس ورا
- `services/loan_service.py:202-208` — بيفحص `get_previous_month_key()` بس، بالرغم من إن
  الـ docstring بيقول إن المتأخرات "تفضل ظاهرة".
- **السيناريو**: قسط يونيو مدفعتوش → يختفي تمامًا من شاشة المتأخرات أول ما أغسطس يبدأ.

### 1.6 🟠 استعلامات الأحداث بـ `limit` من غير `order_by`
- `services/event_store.py:220-225` (limit=200) و `248-255` (limit=500)
- Firestore بيرجع بترتيب doc-id (UUID = عشوائي فعليًا)، فالقص عشوائي **قبل** الترتيب في بايثون.
- بيكسر: `tool_lifecycle_diagnostics.py:114-131` (تقرير الـ Payload بقى كلام مش حقيقي)،
  `self_state_engine.py:62-67` (تحذيرات تعارض وهمية → `attention_needed`)،
  `self_diagnosis.py:83-145` (عدادات 30 يوم بتنقص عشوائي).
- نفس النمط في `firebase_service.py:1179,1302,1341` — `limit(500)` من غير ترتيب،
  يعني بعد 500 ملاحظة الملاحظات الجديدة ممكن ببساطة ما تظهرش خالص.

---

## 2) التذكيرات مش بتوصل

### 2.1 🔴 التذكيرات اليومية المتكررة عمرها ما بتضرب — **مؤكدة**
- `main.py:684-691` (الشرط) + `main.py:862-863` (التسجيل)
- الشرط بيطلب `now.minute == scheduled_minute` **بالظبط**، والـ job متسجل
  `'interval', minutes=15`. الـ docstring نفسه لسه بيقول "كل دقيقة" — الشرط اتكتب لـ polling كل دقيقة.
- **السيناريو**: البوت بدأ 10:07 → الـ job بيشتغل :07/:22/:37/:52 للأبد. تذكير "يوميًا 08:00"
  محتاج `minute == 0` — عمره ما هيحصل. والمحاذاة بتتغير مع كل restart.

### 2.2 🟠 توقيت القاهرة متكتب ثابت UTC+3 — غلط نص السنة
- `main.py:686` و `services/claude_service.py:1310`
- مصر رجّعت التوقيت الصيفي 2023: القاهرة UTC+3 في الصيف و **UTC+2 في الشتا**.
- باقي المشروع بيستخدم `ZoneInfo("Africa/Cairo")` صح — النقطتين دول بس بيبنوا zone ثابت.
- **السيناريو**: من آخر أكتوبر لآخر أبريل كل الأوقات المعروضة متقدمة ساعة، فتقوله "غلط عدّله"
  وتخرب داتا كانت صح.

### 2.3 🟠 تذكيرات `/remind_daily` بتضيع مع كل restart
- `services/scheduler_service.py:23-220` + `main.py:357` — `BackgroundScheduler` عادي
  (job store في الذاكرة)، مفيش أي حاجة بتحفظ الـ jobs أو تعيد بنائها عند البدء.
- الـ import المهجور `from services.reminder_service import get_recurring_reminders`
  في `scheduler_service.py:12` هو أثر الخطوة الناقصة دي.

### 2.4 🟠 تذكيرات المرة الواحدة عايشة في ملف محلي بس
- `services/reminder_service.py:16,45-79` + `main.py:635-650`
- `add_reminder` بيكتب في `second_brain.json` **و** Firestore، لكن `check_reminders_job`
  بيقرا من الملف المحلي **بس**. `firebase_get_pending_reminders` متستوردة ومش متنادية أبدًا.
- **السيناريو**: "ذكرني بعد ساعتين" → deploy بعد نص ساعة → الفايل سيستم بيتصفّر →
  التذكير ضاع، رغم إن نسخة منه قاعدة في Firestore مش بتتقرا.

### 2.5 🟡 `clear_old_reminders` مستحيل يمسح حاجة
- `services/reminder_service.py:145-165` — نفس مشكلة naive/aware، والـ bare except
  بيخلي التذكير **يفضل**. والعداد بيتحسب بعد إعادة الإسناد فبيقول 0 دايمًا. ومفيش حد بيناديها أصلًا.

---

## 3) فقدان بيانات

### 3.1 🔴 الموديل يقدر يمسح مشروع إنتاج نهائي من غير أي حارس — **مؤكدة**
- `services/firebase_service.py:856-864` (`delete_bahr_project`)، متسجلة كأداة للموديل
  في `claude_service.py:1608-1610`
- **مقارنة مباشرة**: `update_bahr_project` (سطر 846) اتحطلها حارس وجود في أوديت 4 أغسطس.
  أخوها المدمر مخدش حاجة. مفيش soft-delete (بالرغم إن الجراف خد soft-delete في سطر 119)،
  و `projects` مش في ليستة الـ backup.
- Firestore `delete()` على مستند مش موجود بينجح، فمعرّف غلط بيرجع "تم الحذف".

### 3.2 🟠 الذاكرة الدائمة: read-modify-write عبر نداء LLM بيستغرق ثواني
- `services/memory_service.py:22-26` — بيقرا الملخص، ينادي `summarize_memory()` (شبكة، ثواني)،
  وبعدين يكتب فوق بـ `set()` كامل. مع `threaded=True` (`bot.py:25`)، رسالتين متقاربتين
  (نص + صوت مثلًا) الاتنين بيقروا نفس الملخص القديم، واللي بيخلص آخرًا بيمسح التاني.

### 3.3 🟠 قص المحادثات بيرمي رسايل
- `services/firebase_service.py:184-191` — بيقرا `messages`، ولو ≥200 بيكتب `msgs[-100:]`.
  أي `ArrayUnion` من thread تاني بين الـ `get()` والـ `update()` بيتمسح.
  والبلوك كله في `except Exception: pass`.

### 3.4 🟠 `graph_edit_node` بيفقد معلومات
- `services/firebase_service.py:93-100` — قراءة، إضافة في بايثون، `set()` للمستند كله.
  تعديلين متزامنين = واحد بيضيع بصمت، والخاسر بيقول "تم".

### 3.5 🟡 الـ backup مالوش مسار استرجاع
- `services/backup_service.py:159-164` — `default=str` بيحوّل Timestamp/GeoPoint لنصوص
  بلا رجعة، والـ doc ID متحطوط جوه جسم المستند كـ `_doc_id`. مفيش سكريبت restore في المشروع كله.

---

## 4) الرد نفسه (Claude API)

### 4.1 🟠 اللوب بيعامل أي `stop_reason` مش `tool_use` كإجابة نهائية — **مؤكدة**
- `services/claude_service.py:1908-1913`
- `TOOLS` فيها `web_search_20250305` (سطر 834). دورة server-tool طويلة ممكن تنتهي بـ
  `pause_turn` → الكود بيرجعها كإجابة نهائية بدل ما يكمّل. نفس الحكاية مع `max_tokens`
  (والـ `max_tokens=2048` ضيق جدًا مع إن الـ system prompt بيطلب لصق تقارير كاملة حرفيًا)
  و `refusal` بيرجع "تمام." الملفقة.
- ولو الموديل خلص التوكنز وهو بيكتب `tool_use`، الأداة **مش بتتنفذ خالص** رغم إنه قالك هيعملها.

### 4.2 🟠 مفيش تقطيع لحد الـ 4096 حرف بتاع تليجرام — **مؤكدة**
- مفيش أي منطق splitting/chunking في المشروع كله (اتأكدت بالبحث).
- `handlers/document_handler.py:155,270`, `handlers/voice_handler.py:73`
- **السيناريو**: DXF فيه 100+ قياس → التقرير يعدّي 4096 → استثناء →
  المستخدم يشوف "الملف متشفر أو تالف" وهو سليم تمامًا.

### 4.3 🟠 `tool_choice` مفروض على `web_search` بيرجّع 400
- `services/claude_service.py:1855-1871` — `real_tool_names` شاملة `"web_search"`،
  ومالهاش `input_schema` فـ `required_args` = `[]` → الكود بيفرضها. فرض server tool
  عبر `tool_choice` مش مدعوم → 400 للرسالة كلها.
- **السيناريو**: "استخدم web_search وشوف أسعار الرخام" — بالظبط الحالة اللي الفيتشر
  اتعمل عشانها — بترجع "❌ حصلت مشكلة".

### 4.4 🟡 كشف الأدوات الصريح بيماتش substring خام
- `services/tool_lifecycle_diagnostics.py:64-67` — أسماء الأدوات بـ `\b` صح، لكن كلمات
  التشغيل بـ `trigger in user_message`: `"use"` بيماتش جوه "because"/"house".
- **السيناريو**: "because get_adam_self_state failed yesterday" → بيفرض تشغيل الأداة دي فعلًا.

---

## 5) أمان وخصوصية

### 5.1 🟠 مسار حقن أوامر من طرف تالت (prompt injection)
- `services/claude_service.py:1738-1766` — `get_eye_expert_logs` بيرجع أسئلة/إجابات عملاء
  من بوت واتساب عام كـ `tool_result` نصي، في محادثة أدواتها فيها
  `delete_project`, `delete_all_reminders`, `update_eye_expert_prompt`, `dispatch_agent_task`.
  مفيش أي علامة إن المحتوى ده غير موثوق.
- **السيناريو**: عميل خارجي يبعت لعين الخبير رسالة مصاغة كأمر لـ ADAM؛ لما تقول
  "وريني آخر أسئلة العملاء"، النص ده بينزل في سياق الموديل كناتج أداة ويقدر يوجّه استدعاءات الأدوات.

### 5.2 🟡 التوكن في الـ query string + مقارنة غير ثابتة الزمن
- `main.py:738-740` — `request.args.get("token")` بيخلي السر يقع في لوجات البروكسي
  والراوتر وهيستوري المتصفح على ناحية Make.com. والمقارنة `!=` بدل `hmac.compare_digest`.
- التصميم fail-closed نفسه ممتاز — دي النقطتين الباقيتين بس.

### 5.3 🟡 مدخلات الأدوات بتتكتب كاملة في اللوج
- `services/claude_service.py:972` — `المدخلات: {tool_input}` (مصاريف، أسماء عملاء، تليفونات)
- **خبر كويس**: فحصت اللوج الحالي — **مفيش أي مفاتيح API ولا توكنز ولا أرقام تليفونات فيه دلوقتي.**
  المشكلة هيكلية (هيتسجلوا لما الأدوات دي تتستخدم)، مش تسريب واقع دلوقتي.

### 5.4 🟠 ملفات وقت التشغيل متتبعة في git
- `bahr_agent.log` (245KB، متتبع ومعدّل دلوقتي)
- `project_tree.txt` (**748KB**)
- ملف فاضي اسمه حرفيًا `git` (0 بايت)
- `config.json` (فيه الـ chat_id الشخصي بتاعك)
- `.gitignore` مغطي `.env` و `second_brain.json` و `memory_cache.json` بس.

---

## 6) أعطال بتتبلع أو بتتكرر

### 6.1 🟠 تنبيه بيضيع للأبد لو الإرسال فشل مرة
- `services/project_status_alerts.py:106-108` و `services/tool_health_alerts.py:122-124`
- في فرع فشل الإرسال، الكود **لسه** بيكتب `last_status = current_status`. الدورة الجاية
  بتشوف prev==current → "مفيش انتقال" → مفيش إعادة محاولة. وده بيناقض تعليق الموديول نفسه.
- **السيناريو**: مشروع بقى `delayed`، الإرسال ضربه timeout واحد (وده حصل فعلًا 4 أغسطس)
  → التنبيه عمره ما هيتبعت ولا هيتعاد.

### 6.2 🟠 تنبيهات بتتكرر كل 10 دقايق لو الكتابة فشلت
- `main.py:545-546` + `services/agent_orchestration.py:197-207` — `mark_task_reported`
  بيبلع أخطاء Firestore، والـ job كل 10 دقايق → أثناء أي انقطاع، نفس رسالة
  "✅ خلّص التاسك" بتتكرر كل 10 دقايق بلا نهاية. نفس الشكل في `deadline_alerts.py:65-67`.

### 6.3 🟠 عنصر واحد باظ بيوقف كل التذكيرات
- `main.py:645-648` و `669-696` — الـ `try` حوالين اللوب كله، و`reminder['نص']` وصول مباشر
  للمفتاح. مستند واحد ناقص الحقل = انقطاع صامت كامل لكل التذكيرات.
- كمان الإرسال بيحصل **قبل** `mark_reminder_sent_locally` — لو الـ mark فشل، نفس التذكير
  بيتبعت كل 30 ثانية.

### 6.4 🟠 حلقة مراقبة بتعطّل نفسها
- `services/capabilities_registry.py:94-96` → `self_state_core.py:243-247` →
  `tool_health_engine.py:49-57`
- `_probe_get_adam_self_state` بيشغّل `compute_self_state_core` اللي بيـ stream
  **كل** مجموعتي `tool_health_checks` و `tool_failures_log`. مفيش أي job تنظيف/TTL ليهم.
- الزمن متقاس ~3.3 ثانية دلوقتي؛ لما يعدّي الـ 5000ms timeout → النتيجة "timeout" تتسجل →
  مرتين في 24 ساعة = `get_adam_self_state` يتصنف DEGRADED → **تتنبّه على عطل المراقبة نفسها صنعته.**
- المشروع ده خد أزمة ResourceExhausted حقيقية قبل كده من نفس نمط القراءة ده.

### 6.5 🟡 backup "ناجح" وهو فاضي
- `services/backup_service.py:54-70,153-174` — `export_collection` بيرجع `[]` سواء المجموعة
  فاضية فعلًا أو Firestore مقطوع. `run_backup` بيسجل `success: True` والإشعار بيقول
  "Backup ✅ تم بنجاح" مع `0 docs`.

---

## 7) كود ميت / متناقض

- **~50 سطر كود رؤية ميت** جوه `summarize_memory` (`claude_service.py:2252-2304`) —
  بقايا `analyze_with_vision` قديمة اتمسح سطر الـ `def` بتاعها. بتناقض النسخة الحية
  (max_tokens 400 مقابل 800، prompt مختلف). لغم لأي تعديل جاي.
- **AdamMind / ExecutiveBrain تحليل النية no-op** — `executive_brain.py:243-266`:
  `_stage_plan` بيرجع `capability="claude_agentic"` دايمًا؛ نتيجة `IntentAnalysis`
  (وفيها نداء Haiku في `adam_mind.py:179-227`) بتتحط في `context["intent"]` اللي محدش بيقراه.
  **كل رسالة غامضة بتدفع نداء موديل زيادة + ~300ms والناتج بيترمي.**
- **`morning_brief.send_morning_brief`** (`morning_brief.py:188-197`) — المسار الوحيد اللي
  بيعمل verify — محدش بيناديه.
- **تسريب pending verification**: `main.py:622-633` و `150-157` بيبعتوا من غير
  `verify_and_finalize` → الجملة المعتمدة بتتعلق في `_pending_verifications` وتتلزق
  على رد تاني مالوش علاقة، وتسجل `verbatim_mismatch` كذّاب (بيلوّث عدادات الصحة في 1.6).
- **سطح scheduler ميت**: `add_interval_reminder`, `add_smart_loan_reminder`، وكل مخزن
  التذكيرات المتكررة المحلي في `reminder_service.py:179-252`.
- **`check_and_send_reminders`** (`reminder_service.py:127-137`) — الإرسال الفعلي
  متعلّق كـ comment (سطر 133) لكن `mark_reminder_sent_locally` بيشتغل. فخ جاهز لأي caller جديد.
- **تبعيات ميتة**: `schedule==1.2.2` و `pytz==2024.1` محدش بيستوردهم، و`gunicorn` محدش بينده عليه.
- **`pytest` مش متسطب ولا في requirements** رغم وجود 28 ملف اختبار
  (كلهم standalone بـ `__main__`، فبيشتغلوا فرادى).

---

## 8) حاجات سليمة (اتفحصت وطلعت كويسة)

- ✅ **مفيش أي أخطاء syntax** — كل ملفات المشروع بتتـ compile نضيف.
- ✅ **مفيش أسرار في اللوج** — فحصت `bahr_agent.log` كله: صفر مفاتيح API، صفر توكنز، صفر تليفونات.
- ✅ **مفيش أي سر متكوميت في تاريخ git** — `.env` عمره ما اتتبع.
- ✅ **معرّفات الموديلات صح ومحدّثة** — `claude-sonnet-5` و `claude-haiku-4-5-20251001`،
  و`thinking: {"type": "adaptive"}` + `output_config` أشكال صحيحة على Sonnet 5.
- ✅ **prompt caching متظبط صح** — البلوك الثابت شايل `cache_control`، والتوقيت المتغير
  في البلوك غير المكاشّ، 3 نقاط كسر (≤4).
- ✅ **`event_store.py`** فيه تحقق إجباري للحقول، وذرية Firestore batch حقيقية في
  `record_event_with_write`، وبيرمي استثناء (مش بيبلع) لما Firestore يقع.
- ✅ **`supabase_service.py`** منضبط — التفرقة بين `None` و `[]` صح تمامًا.
- ✅ **`update_guard.py`** بيقفل ثغرة المستندات الوهمية للتحديثات فعلًا (بس مش للحذف — 3.1).
- ✅ **الحارس fail-closed للـ endpoints** تصميمه صح.
- ✅ **مرونة الشبكة مع تليجرام** (`safe_typing`/`safe_reply`) معمولة بعناية.
- ✅ **`atomic_io.py`** بيستخدم temp-file + `os.replace` صح (ناقصه `fsync` بس).
- ✅ **مسار كتابة القروض** معماريًا كويس: نقطة كتابة واحدة + event sourcing + وقفة تعارض قبل الكتابة.
- ✅ **طبقة التنبيهات** (transition-only + cooldowns) مصممة كويس.
- ✅ **اختبارات شغالة**: `test_endpoint_security.py` 4/4 عدّى، `test_price_base.py` 9/9 عدّى.
  (`test_update_guards.py` بيقع بـ `UnicodeEncodeError` على كونسول ويندوز cp1252 — مشكلة عرض مش منطق.)
- ✅ **مفيش async** في المشروع (telebot متزامن بـ threads) — فمفيش مشاكل event-loop،
  لكن مخاطر الـ threads حقيقية.

---

## الترتيب المقترح للإصلاح

| # | الإصلاح | الملف | الأثر |
|---|---------|-------|-------|
| 1 | ضيّق `_find_program` (مطابقة كاملة/أسماء مستعارة صريحة) | `loan_service.py:96` | يمنع تسجيل قسط على قرض غلط |
| 2 | ضيف `GITHUB_TOKEN`/`GITHUB_REPO` + وسّع `COLLECTIONS` | `.env`, `backup_service.py:33` | أول نسخة احتياطية حقيقية |
| 3 | صلّح naive/aware في `get_upcoming_followups` | `claude_service.py:1573` | متابعات العملاء ترجع تشتغل |
| 4 | خلي الـ recurring job كل دقيقة + `now_cairo()` | `main.py:686,862` | التذكيرات اليومية تضرب |
| 5 | حارس وجود لـ `delete_bahr_project` | `firebase_service.py:856` | يمنع حذف مشروع نهائي |
| 6 | ضيف `AGENT_TASKS_SECRET`/`EYE_EXPERT_SECRET` | `.env` | تشغيل عين الخبير و agent-tasks |
| 7 | اعمل الـ composite index | Firebase Console | البحث في الملاحظات يشتغل |
| 8 | متكتبش `last_status` لما الإرسال يفشل | `project_status_alerts.py:106` | التنبيهات متضيعش |
| 9 | ضيف `order_by` لكل استعلامات `limit` | `event_store.py`, `firebase_service.py` | تشخيص وأحداث موثوقة |
| 10 | ضيف تقطيع 4096 حرف في نقطة إرسال واحدة | `bot.py` | ردود طويلة توصل |
| 11 | عالج `pause_turn`/`max_tokens` صح | `claude_service.py:1908` | ردود مش مقطوعة |
| 12 | `git rm --cached` للوج و project_tree و `git` | `.gitignore` | ~1MB زبالة تخرج من الريبو |
