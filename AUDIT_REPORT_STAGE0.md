# Audit Report — Stage 0 (قبل Event Schema & Store)
تاريخ: 2026-07-24
النطاق: أدوات ADAM الحالية + مسارات الكتابة + الاستعداد لمشروع ADAM Self-State & Observation System

---

## 1. الخريطة المعمارية الحالية

```
Telegram/Flask ──▶ adam_runtime.py (BahrEvent) ──▶ executive_brain.py (ExecutiveBrain)
                                                          │
                                                          ├─ scheduler events ─▶ handlers مباشرة (morning_brief, loans check...)
                                                          │
                                                          └─ user events ─▶ ask_claude_agentic() [services/claude_service.py]
                                                                                  │
                                                                     (loop: tool_use → _execute_tool)
                                                                                  │
                                                                     services/claude_service.py: _execute_tool()
                                                                                  │
                                        ┌─────────────────────────────────────────┼──────────────────────────────┐
                                        ▼                                         ▼                              ▼
                          services/loan_service.py                services/firebase_service.py      firestore_db مباشرة
                          (منطق الأقساط)                            (طبقة رفيعة فوق Firestore)         (بعض الأدوات بتتخطى حتى الطبقة دي)
                                        │                                         │                              │
                                        └─────────────────────────────────────────┴──────────────────────────────┘
                                                                                  ▼
                                                                              Firestore
```

**ملاحظة تسمية مهمة:** فيه كلاس اسمه `BahrEvent` في [executive_brain.py](executive_brain.py:79) — ده تمثيل لرسالة/جدولة داخلة للـ Executive Brain، **مش** نفس مفهوم الـ "Event" المطلوب في مشروع Self-State (حدث بحقلي `entity`/`attribute` قابل للرصد والتخزين التاريخي). لازم اسم مختلف تمامًا للـ Event Schema الجديد (مثلاً `ObservedEvent` أو `DomainEvent`) عشان منلخبطش الاتنين في نفس الكودبيز.

**النتيجة الأهم:** مفيش أي مفهوم Event Store / Observer / Self-State موجود في الكود دلوقتي على الإطلاق. البنية الحالية كلها: أداة → تنفيذ مباشر → كتابة فورية → رد نصي للموديل. مفيش أي طبقة وسيطة بين "الموديل قرر يستخدم أداة" و"البيانات اتغيرت فعليًا".

---

## 2. جرد كامل للأدوات (كلها معرّفة في [services/claude_service.py](services/claude_service.py) — الـ TOOLS list وdispatch في `_execute_tool`)

| الأداة | نوع | تكتب فين | ملاحظات |
|---|---|---|---|
| list_graph_nodes | قراءة | — | |
| add_graph_node | **كتابة** | firebase_service.graph_add_node | |
| edit_graph_node | **كتابة** | firebase_service.graph_edit_node | |
| delete_graph_node | **حذف** | firebase_service.graph_delete_node | بدون تأكيد |
| create_reminder | **كتابة** | reminder_service.add_reminder | |
| add_expense | **كتابة** | firebase_service.add_expense | فيها منطق تنبيه مالي جوه نفس الأداة (سقف 40,000) — side effect إضافي غير موثق كـ event |
| list_expenses | قراءة | — | |
| expense_summary | قراءة | — | |
| **loan_overview** | قراءة | — | ✅ read-only فعلاً، زي ما هو متوقع |
| **loan_month_installments** | قراءة | — | ✅ read-only فعلاً |
| **loan_mark_paid** | **كتابة مباشرة ⚠️** | loan_service → firebase_service.save_loan_paid_status | **مفصّلة بالكامل تحت (قسم 3) — دي الأداة اللي طلبتوا التركيز عليها** |
| save_memory_note | **كتابة** | firebase_service.save_memory_note | |
| get_graph_node_details | قراءة | — | |
| get_weather | قراءة | — | API خارجي |
| update_memory_note | **كتابة** | firebase_service.update_memory_note | |
| get_upcoming_deadlines | قراءة | — | |
| save_memory_note_with_deadline | **كتابة** | firebase_service.save_memory_note_with_deadline | |
| delete_memory_note | **حذف** | firebase_service.delete_memory_note | بدون تأكيد |
| search_memory_notes | قراءة | — | |
| list_memory_notes | قراءة | — | |
| list_reminders | قراءة | — | |
| delete_reminder | **حذف** | firebase_service.delete_reminder | بدون تأكيد |
| delete_all_reminders | **حذف جماعي ⚠️** | firebase_service.delete_all_reminders | حذف كل التذكيرات بضربة واحدة، بدون أي تأكيد يدوي |
| get_human_model | قراءة | — | |
| update_human_model | **كتابة** | firebase_service.update_human_model | |
| get_bahr_projects | قراءة | — | |
| get_bahr_sites | قراءة | — | |
| get_project_details | قراءة | — | |
| create_recurring_reminder | **كتابة** | firebase_service.save_recurring_reminder | |
| list_recurring_reminders | قراءة | — | |
| delete_recurring_reminder | **حذف** | firebase_service.delete_recurring_reminder_db | بدون تأكيد |
| get_backup_status | قراءة | — | HTTP خارجي (GitHub) |
| add_client_followup | **كتابة** | `firestore_db` **مباشرة** جوه claude_service.py (بدون المرور بـ firebase_service.py أصلاً) | |
| update_client_followup | **كتابة** | `firestore_db` **مباشرة** | نفس الملاحظة |
| get_client_followups | قراءة | — | |
| get_upcoming_followups | قراءة | — | |
| create_project | **كتابة** | firebase_service.create_bahr_project | |
| update_project_details | **كتابة** | firebase_service.update_bahr_project | |
| delete_project | **حذف** | firebase_service.delete_bahr_project | بدون تأكيد |
| add_site | **كتابة** | firebase_service.add_bahr_site | |
| delete_expense | **حذف** | firebase_service.delete_expense | بدون تأكيد |
| update_project_status | **كتابة** | `firestore_db` **مباشرة** | نفس الملاحظة (raw Firestore) |
| get_eye_expert_prompt | قراءة | — | |
| update_eye_expert_prompt | **كتابة** | `firestore_db` **مباشرة** | نفس الملاحظة |
| get_eye_expert_logs | قراءة | — | |

**خلاصة الجرد:** من ~45 أداة، حوالي 22 بتكتب أو بتحذف بيانات مباشرة، و4 منهم (`add_client_followup`, `update_client_followup`, `update_project_status`, `update_eye_expert_prompt`) بتتخطى حتى طبقة `firebase_service.py` الرفيعة وتكلم Firestore خام جوه ملف الـ dispatch نفسه — أسوأ حالة من ناحية القابلية للرصد المستقبلي.

---

## 3. تعمّق كامل في `loan_mark_paid` (المثال اللي طرحتوه)

### مسار التنفيذ الكامل (الوحيد، مفيش مسار بديل)

1. المستخدم يبعت رسالة → `ask_claude_agentic()` ([claude_service.py:1328](services/claude_service.py:1328))
2. الموديل يقرر يستخدم أداة `loan_mark_paid` بمدخلات `{program_name, month_key?, paid?}`
3. `_execute_tool("loan_mark_paid", ...)` ([claude_service.py:815](services/claude_service.py:815)) بينده مباشرة:
   ```python
   ok, msg = loan_service.mark_installment_paid(program_name, month_key, paid)
   ```
4. `loan_service.mark_installment_paid()` ([loan_service.py:193](services/loan_service.py:193)):
   - بيدور على البرنامج بالاسم (fuzzy match)
   - بيحدد الشهر (الحالي لو مفيش month_key)
   - بينده `set_paid(program_id, index, paid)`
5. `set_paid()` ([loan_service.py:131](services/loan_service.py:131)) بينده `firebase_service.save_loan_paid_status(key, paid)`
6. `save_loan_paid_status()` ([firebase_service.py:613](services/firebase_service.py:613)):
   ```python
   firestore_db.collection(LOANS_COLLECTION).document("paid_status").set(
       {f"paid.{key}": paid}, merge=True
   )
   ```
   **ده الكتابة الفعلية الوحيدة.** merge على dotted path لمفتاح واحد جوه map واحد.

### تأكيد: هل فيه مسار تاني للأقساط؟
- `main.py` فيه زرار Telegram اسمه `loans_month` ([main.py:137](main.py:137)) — لكنه **read-only**، بيبعت رسالة نصية لـ `runtime.run()` زي أي رسالة مستخدم عادية، فبيمر بنفس المسار اللي فوق (مفيش bypass).
- `main.py` فيه `check_loans_job()` ([main.py:281](main.py:281)) — job مجدول يوميًا، لكنه **قراءة فقط** (بيقرأ الأقساط المستحقة ويبعت تنبيه)، مش بيكتب حاجة.
- `executive_brain.py` عنده intent اسمه `get_loans` ([executive_brain.py:105](executive_brain.py:105)) لكنه بيوجّه كل حاجة لنفس مسار Claude Agentic، مفيش direct handler منفصل للأقساط.
- **خلاصة:** ✅ `loan_mark_paid` هو فعلاً المدخل الوحيد لتغيير حالة الأقساط. مفيش مسار مخفي أو مزدوج. ده خبر كويس — التحويل لـ Command API محتاج يعدّل نقطة واحدة بس.

### مشاكل الـ schema الحالي للأقساط
- **مفيش تاريخ (history) خالص.** الـ Firestore document (`loans/paid_status`) عبارة عن map واحد `{program_id_index: bool}`. أي كتابة بتدوس على القيمة القديمة **بدون ما تسيب أي أثر**: مفيش `updated_at`, مفيش `updated_by`, مفيش القيمة السابقة، مفيش سبب.
- **مفيش هوية للحدث نفسه.** لو حصل خطأ من الموديل (غلط في الشهر، غلط في اسم البرنامج) وعلّم قسط غلط، مفيش أي سجل يوضح إن ده حصل ولا إمتى ولا ليه.
- **الـ "identity_key" الحالي** (`program_id_index`, مثلاً `valu_0`) هو نفسه فكرة الـ normalized identity المطلوبة في مرحلة 3 (Conflict Observer) — يعني موجود ضمنيًا لكن مش مُعرّف كـ concept مستقل، وده هيسهّل ربطه بالـ `identity_key = normalized_program + billing_period` اللي انتوا مخططينله.
- **الـ `_find_program()` fuzzy match** ([loan_service.py:92](services/loan_service.py:92)) بيقبل أي substring تطابق اسم أو id البرنامج. لو الموديل بعت اسم غامض ممكن يطابق برنامج غلط بصمت (مفيش تحذير لو فيه أكتر من تطابق محتمل — بياخد أول واحد بس).

---

## 4. ملاحظات حرجة (Critical Findings)

1. **⚠️ `loan_mark_paid` بيكتب بدون أي رقابة أو تسجيل حدث** — مؤكد 100%، زي ما وصفتوا في المثال. المسار الوحيد، لكن ولا خطوة واحدة فيه بتعمل audit trail.

2. **⚠️ 4 أدوات بتتخطى حتى الـ abstraction الرفيع (`firebase_service.py`) وتكتب Firestore خام:** `add_client_followup`, `update_client_followup`, `update_project_status`, `update_eye_expert_prompt`. لو الـ Observer اتبنى فوق `firebase_service.py` كنقطة اعتراض، الأربعة دول هيتخطوه تلقائيًا لأنهم أصلاً مش بيمروا عليه. لازم أي تصميم لـ Command API يعترض عند نقطة الدخول (`_execute_tool` dispatch) مش عند طبقة `firebase_service.py`، أو يوحّد كل الكتابة تمر من مكان واحد أولاً.

3. **⚠️ عمليات حذف كتير بدون أي تأكيد يدوي:** `delete_graph_node`, `delete_memory_note`, `delete_reminder`, `delete_all_reminders` (حذف جماعي!), `delete_project`, `delete_expense`, `delete_recurring_reminder`. أي واحدة فيهم ممكن الموديل ينفذها من رسالة واحدة غامضة من غير أي "متأكد؟". ده نفس فلسفة الـ Conflict Resolution (مرحلة 4) بس أخطر لأنه حذف مش تعارض بيانات — يستاهل يتحط في نفس دائرة "يوقف وياخد تأكيد يدوي من أحمد".

4. **مفيش أي concept لـ Event/Observer/Self-State في الكود كله حاليًا.** البناء من الصفر تمامًا. الحاجة الوحيدة القريبة هي `logger.info(f"🔧 الموديل طلب أداة...")` ([claude_service.py:687](services/claude_service.py:687)) — سطر log نصي في ملف (`bahr_agent.log`)، مش structured event، ومش مخزّن في Firestore، ومفيش schema له.

5. **نمط الأخطاء الموحّد `except Exception as ex: result = f"❌ خطأ: {ex}"`** منتشر في كل الأدوات تقريبًا. ده بيرجع نص للموديل بس، مفيش أي حالة "فشل" منظّمة يقدر أي Observer مستقبلي يستهلكها أو يفرّق بها بين "الكتابة نجحت" و"الكتابة فشلت".

6. **كود ميت: `handlers/command_handler.py`** — مش متربط بأي حاجة في `main.py`/`bot.py`/`adam_runtime.py` (اتأكدت بالبحث، صفر استيراد ليه في أي مكان)، وبيستورد `services.task_service` اللي **مش موجود في المشروع أصلاً** — لو حد حاول يشغّله هيكسر فورًا بـ `ImportError`. مش خطر على مشروع Self-State (مفيش حد بيستخدمه)، بس يستاهل تنظيف لاحقًا خارج نطاق الأولوية دي.

7. **`update_human_model`** موجودة كأداة كتابة مباشرة كمان، خارج نطاق v0.1 (الأقساط بس)، بس هتحتاج نفس المعاملة لما نوصل لمرحلة التوسع.

---

## 5. العمليات المرشحة للتحويل لـ Command API (خريطة كاملة، مش تنفيذ الآن)

**نطاق v0.1 (الأقساط فقط — ده اللي هنشتغل عليه دلوقتي):**
- `loan_mark_paid` → يتحول لـ `loan_record_installment` / `loan_update_installment` عبر Command API زي المتفق عليه.
- `loan_overview`, `loan_month_installments` → تفضل زي ما هي، read-only، بدون أي تعديل.

**للمستقبل (بعد التوسع حسب مرحلة 8: Loans → Expenses → Projects → Memory):**
- Expenses: `add_expense`, `delete_expense`
- Projects: `create_project`, `update_project_details`, `delete_project`, `add_site`, `update_project_status` (ودي كمان محتاجة تتنقل من raw Firestore لـ `firebase_service.py` الأول قبل أي حاجة تانية)
- Client followups: `add_client_followup`, `update_client_followup` (نفس ملاحظة raw Firestore)
- Memory: `save_memory_note`, `update_memory_note`, `delete_memory_note`, `save_memory_note_with_deadline`
- Human Model: `update_human_model`
- Reminders: `create_reminder`, `delete_reminder`, `delete_all_reminders`, `create_recurring_reminder`, `delete_recurring_reminder`
- Graph: `add_graph_node`, `edit_graph_node`, `delete_graph_node`
- Eye Expert config: `update_eye_expert_prompt`

---

## 6. توصية للخطوة الجاية (مرحلة 1: Event Schema & Store)

- الـ Event Schema الجديد لازم يستخدم اسم مختلف عن `BahrEvent` الموجود (اقتراح: `ObservedEvent`).
- نقطة الاعتراض الصح لمرحلة 1+2 هي **جوه `_execute_tool()` في `claude_service.py`** (نقطة الدخول الموحدة الفعلية لكل الأدوات)، مش جوه `firebase_service.py` — لإن 4 أدوات بتتخطى `firebase_service.py` أصلاً (نقطة 2 فوق).
- الـ `identity_key` بتاع الأقساط (`program_id_index`) جاهز فعليًا كمفهوم، محتاج بس يتوثق رسميًا كجزء من الـ Event Schema.
- ابدأ بـ `loan_mark_paid` بس (زي ما اتفقنا Scope v0.1)، وسيب باقي الـ 21 أداة الكاتبة زي ما هي لحد ما نوصلهم بالترتيب في مرحلة 8.

---

**الخلاصة:** المثال اللي ذكرتوه (`loan_mark_paid` بيكتب من غير رقابة) مؤكد ودقيق 100%، وهو فعلاً أوضح نقطة خطر في الكود الحالي. الخبر الكويس: مسار الأقساط بسيط ومفرد (مفيش تعقيد مخفي)، فالتحويل لـ Command API في مرحلة 2 هيبقى تعديل مركّز في مكان واحد. الخبر اللي يستاهل انتباه زيادة: فيه 4 أدوات تانية (مش أقساط) بتكتب Firestore خام بره حتى الـ abstraction البسيط الموجود — مش أولوية v0.1 لكن يستاهل يتسجل عشان ميتنسيش وقت التوسع.
