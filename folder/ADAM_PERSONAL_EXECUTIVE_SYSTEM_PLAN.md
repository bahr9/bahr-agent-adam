# ADAM — Personal Executive System Plan

**Status:** Draft  
**Purpose:** تحويل ADAM من مساعد محادثة عام إلى نظام تنفيذي شخصي طويل الأمد، مصمم خصيصًا لأحمد وشركة Bahr Designs.

---

## 1. Current Position — أين نقف الآن؟

نحن حاليًا في مرحلة مراجعة إصلاحات **Token Optimization** التي طُلبت من Claude.

### الملفات التي تأثرت

1. `executive_brain.py`
   - تم تقليل Conversation History من:
     - Firestore limit: `50` إلى `20`
     - Claude formatted history: `15` إلى `8`
   - تم إضافة `LearningDecision` وفلتر للرسائل القصيرة.

2. `claude_service.py`
   - تم تقليص `memory_summary` إلى آخر `800` حرف.

3. ملف الذاكرة الذي يحتوي على `summarize_memory`
   - تم قطع `assistant_reply` عند `400` حرف.

### الإصلاحات المطلوبة من Claude

- إعادة History مؤقتًا إلى:
  ```python
  stored = get_conversation_history(event.chat_id, limit=50)
  context["history"] = format_history_for_claude(stored, limit=15)
  ```

- إلغاء:
  ```python
  memory_summary[-800:]
  ```

- إلغاء القطع الأعمى لـ `assistant_reply` عند 400 حرف.

- الإبقاء على `LearningDecision`، مع منع استبعاد الرسائل القصيرة المهمة، مثل:
  - اعتماد قرار
  - رفض
  - تصحيح
  - اختيار
  - تغيير حالة
  - قرار معماري
  - رد يعتمد معناه على الرسالة السابقة

- إنشاء Backup.
- عرض Diff واضح.
- عدم تغيير Architecture أو Routing أو System Prompt.
- تشغيل الاختبارات الحالية.

### الخطوة التالية المباشرة

**مراجعة تنفيذ Claude للتعديلات السابقة قبل فتح أي تطوير جديد.**

يجب أن نتحقق من:

- الملفات التي عدّلها.
- الـ Diff الفعلي.
- عدم وجود تغييرات إضافية غير مطلوبة.
- رجوع السياق والذاكرة إلى السلوك الآمن.
- عدم كسر `LearningDecision`.
- نجاح الاختبارات.
- تجربة آدم عمليًا بمحادثة طويلة ورسائل قصيرة مرتبطة بالسياق.

---

## 2. Core Principle — المبدأ الأساسي

> **Memory Before Optimization.**

ADAM ليس Chatbot عابرًا.  
ADAM كيان تنفيذي طويل الأمد، ووظيفته الأساسية أن يتذكر أحمد، ويفهم السياق، ويكمل من حيث انتهى الحوار.

تقليل الـ Tokens هدف مهم، لكنه يأتي بعد:

1. استمرارية الحوار.
2. حفظ القرارات والحقائق.
3. فهم الرسائل القصيرة المرتبطة بالسياق.
4. دقة التنفيذ.
5. ثم تحسين التكلفة والسرعة.

### القاعدة الذهبية

> **نوفر بعقل، لا نوفر على حساب الذاكرة.**

والتحسين الصحيح يكون عن طريق **اختيار المعلومات الأكثر صلة**، وليس القطع العشوائي حسب عدد الأحرف أو الرسائل.

---

## 3. Vision — الرؤية

تحويل ADAM إلى:

> **Personal Executive Operating System for Ahmed and Bahr Designs**

آدم لا يقتصر على الرد على الأسئلة، بل يجب أن:

- يتذكر.
- يفهم.
- يربط المعلومات.
- يرتب الأولويات.
- يخطط.
- ينفذ.
- يتحقق.
- يتعلم.
- يبادر في الوقت المناسب.

مع الحفاظ على أنه نظام ذكاء اصطناعي، لا يدّعي أنه إنسان أو يمتلك مشاعر بشرية.

---

## 4. What Makes ADAM Exceptional?

### 4.1 Memory Architecture

يجب الفصل بين أنواع الذاكرة بدل وضع كل شيء داخل Chat History أو Summary واحدة.

#### A. Human Model

يحتوي على معلومات طويلة الأمد تساعد آدم على العمل مع أحمد، مثل:

- طريقة التفكير.
- أسلوب التواصل المفضل.
- الأهداف.
- الأولويات.
- نمط اتخاذ القرار.
- التحديات المتكررة.
- طريقة عرض المعلومات المناسبة.

#### B. Business Memory

يحتوي على:

- هوية Bahr Designs.
- الخدمات.
- التسعير.
- معايير الجودة.
- العمليات.
- الموردين والمقاولين.
- العملاء.
- القوالب والسياسات.

#### C. Project Memory

ملف حي لكل مشروع، يشمل:

- العميل.
- الموقع.
- الميزانية.
- نطاق العمل.
- البرنامج الزمني.
- التصميمات.
- المقايسات.
- الدفعات.
- المشتريات.
- الفريق.
- المشاكل.
- المخاطر.
- القرارات.
- آخر حالة مؤكدة.

#### D. Decision Ledger

أي قرار مهم يجب أن يُحفظ ككيان منظم، وليس كسطر مدفون داخل محادثة.

مثال:

```yaml
decision: اعتماد خامة البورسلين X
project: New Obour Apartment
status: accepted
reason: أفضل جودة داخل الميزانية
owner: Ahmed
date: 2026-07-26
source: conversation
```

#### E. Conversation History

سجل المحادثات الكامل، ويُستخدم للاستمرارية القريبة، لكنه ليس المصدر الوحيد للذاكرة.

#### F. Working Memory

سياق مؤقت خاص بالطلب الجاري، وينتهي بعد التنفيذ.

---

## 5. Context Engine

بدل إرسال كل المعلومات أو قصها عشوائيًا، يبني آدم Context حسب الطلب.

### Context Package

1. Core Identity
2. Current User Message
3. Recent Conversation
4. Relevant Memories
5. Active Project State
6. Accepted Decisions
7. Human Model fields المرتبطة
8. Tool Results
9. Current Execution State

### المبدأ

> **Context by relevance, not context by length.**

مثال: عند السؤال عن مشروع العبور، لا يحتاج آدم إلى تاريخ حملات التسويق، لكنه يحتاج:

- آخر حالة للمشروع.
- القرارات المعتمدة.
- البنود المتأخرة.
- تقارير الموقع.
- المشتريات.
- الدفعات.
- آخر رسائل مرتبطة بالمشروع.

---

## 6. Executive Brain

الـ Executive Brain يجب أن يتحول من Pipeline شكلي إلى عقل قرار تنفيذي.

### Pipeline المستهدف

```text
Intake
→ Resolve Context
→ Understand
→ Assess Risk
→ Plan
→ Execute
→ Verify
→ Record
→ Learn
→ Respond
```

### الأسئلة الداخلية قبل التنفيذ

1. ما المطلوب الحقيقي؟
2. هل الطلب يعتمد على سياق سابق؟
3. هل يوجد قرار معتمد يجب احترامه؟
4. ما المعلومات الناقصة؟
5. هل يمكن استخدام Tool؟
6. هل التنفيذ آمن؟
7. كيف يتم التحقق من النجاح؟
8. ماذا يجب تسجيله أو تعلمه؟
9. هل توجد متابعة مستقبلية مطلوبة؟

---

## 7. Capabilities Registry + Phonebook

يجب أن يعرف آدم كل Capability بشكل منظم.

كل Capability يجب أن تحتوي على:

- Name
- Purpose
- Owner agent/service
- Inputs
- Outputs
- Preconditions
- Tool/function
- Verification method
- Failure behavior
- Fallback
- Permissions
- Cost level
- Risk level

### مثال

```yaml
name: create_reminder
purpose: إنشاء تذكير لمرة واحدة
owner: personal_assistant
inputs:
  - title
  - datetime
  - timezone
verification:
  - read created reminder
  - compare title and datetime
failure:
  - return explicit StageError
```

---

## 8. Work Graph

آدم يحتاج خريطة علاقات حية، وليس مجرد قوائم.

```text
Ahmed
└── Bahr Designs
    ├── Projects
    │   ├── Client
    │   ├── Site
    │   ├── Supervisor
    │   ├── Contractor
    │   ├── BOQ
    │   ├── Payments
    │   ├── Materials
    │   ├── Tasks
    │   ├── Risks
    │   └── Decisions
    ├── Suppliers
    ├── Team
    ├── Leads
    ├── Marketing
    └── Company Operations
```

الهدف أن يستطيع آدم الإجابة عن أسئلة مركبة، مثل:

- أي مشروع معرض للتأخير؟
- أي مورد يؤثر على أكثر من موقع؟
- ما القرارات التي تنتظر أحمد؟
- أين يوجد بند منفذ وغير مدفوع؟
- أي عميل ينتظر ردًا؟
- ما المواقع التي لم ترسل تقرير اليوم؟

---

## 9. Specialized Agents

آدم هو المدير التنفيذي، وتحته قدرات متخصصة.

### Proposed Agents

- **Site Agent**
  - تقارير المواقع
  - نسب الإنجاز
  - المخاطر
  - الملاحظات
  - الحضور

- **Commercial Agent**
  - المقايسات
  - التكاليف
  - المستخلصات
  - الهوامش
  - التدفقات النقدية

- **Design Agent**
  - التصميم
  - الاعتمادات
  - الخامات
  - اللوحات
  - ملفات التنفيذ

- **Procurement Agent**
  - الموردون
  - عروض الأسعار
  - الاعتمادات
  - التوريد
  - التأخير

- **Client Agent**
  - المتابعات
  - الاجتماعات
  - الرسائل
  - القرارات المطلوبة
  - رضا العميل

- **Medad — Marketing Agent**
  - المحتوى
  - الحملات
  - Leads
  - النشر
  - التحليل

- **Personal Executive Assistant**
  - المواعيد
  - التذكيرات
  - الأولويات
  - العادات
  - الالتزامات الشخصية

المستخدم يتعامل مع آدم فقط، وآدم ينسق بين القدرات المتخصصة.

---

## 10. Verification System

لا يعتبر آدم العملية ناجحة لمجرد أن Tool تم استدعاؤها.

### Execution States

```text
Requested
→ Planned
→ Executed
→ Verified
→ Recorded
```

### أمثلة

#### Reminder

- تم إنشاء التذكير.
- تم قراءة السجل الناتج.
- تم التأكد من العنوان والوقت والمنطقة الزمنية.

#### Expense

- تم إضافة المصروف.
- تم التحقق من القيمة والتصنيف والتاريخ.
- تم التأكد من ظهوره في الملخص.

#### Project Update

- تم تنفيذ التحديث.
- تم قراءة حالة المشروع بعد التحديث.
- تم مقارنة الحالة المطلوبة بالحالة الفعلية.

---

## 11. Initiative Engine

النقلة الأساسية من مساعد تفاعلي إلى شريك تنفيذي.

### البداية المقترحة

#### Morning Brief

- مواقع اليوم.
- أهم المهام.
- القرارات المطلوبة.
- المتابعات المتأخرة.
- الدفعات.
- المخاطر.
- أول خطوة مقترحة.

#### Site Risk Alerts

- تقرير مفقود.
- بند متأخر.
- خامة غير معتمدة.
- توريد متأخر.
- تعارض بين التقرير والصور.
- مصروف غير موثق.

#### Before-Meeting Brief

- بيانات العميل.
- آخر اتفاق.
- القرارات المفتوحة.
- النقاط الحساسة.
- المطلوب من الاجتماع.

#### End-of-Day Review

- ما تم.
- ما لم يتم.
- ما تأخر.
- ما يحتاج قرارًا.
- ما يجب نقله للغد.

### قاعدة المبادرة

آدم لا يزعج أحمد بكل شيء.

يبادر فقط عندما تكون المعلومة:

- مهمة.
- قابلة للتنفيذ.
- في الوقت المناسب.
- مرتبطة بهدف أو خطر.
- وتحتاج تدخل أحمد فعلًا.

---

## 12. User Experience

آدم يجب أن يعرض **القرار أولًا**.

### Response Pattern

1. الخلاصة أو القرار.
2. السبب المختصر.
3. الإجراء الذي تم أو المقترح.
4. ما يحتاجه من أحمد، إن وجد.
5. حالة التحقق.

### مثال

> لا أنصح ببدء تنفيذ المطبخ اليوم.  
> اعتماد الرخام ومراجعة نقطة الغاز لم يكتملَا.  
> جهزت النقطتين للمراجعة، وأقترح إغلاقهما قبل إصدار أمر التنفيذ.

---

## 13. Token Optimization Strategy

تحسين التكلفة يتم لاحقًا بطريقة مدروسة.

### مقبول

- Relevant Memory Retrieval.
- Structured summaries.
- Project-specific context.
- Decision Ledger.
- Dynamic history expansion.
- إزالة التكرار.
- إرسال Tool results المختصرة.
- Cache للمعلومات الثابتة.
- قياس Tokens مقابل جودة الرد.

### غير مقبول

- آخر 800 حرف.
- أول أو آخر 400 حرف.
- تقليل History للجميع بنفس القيمة.
- اعتبار الرسالة القصيرة غير مهمة.
- حذف معلومات دون معرفة أثرها.
- تحسين Token usage دون Quality Tests.

---

## 14. Success Criteria

### Memory

- يتذكر القرارات المعتمدة.
- لا يكرر سؤالًا تمت الإجابة عنه.
- يفهم رسائل مثل: «تمام اعتمد» و«لا، التاني».
- يستطيع استرجاع سبب القرار، وليس القرار فقط.

### Execution

- يستخدم الأداة الصحيحة.
- يتحقق من النتيجة.
- لا يدّعي التنفيذ دون دليل.
- يسجل التغييرات المهمة.

### Business Value

- يقلل المهام التي ينساها أحمد.
- يكشف المخاطر قبل حدوثها.
- يقلل وقت متابعة المواقع.
- يسرّع تجهيز الاجتماعات والقرارات.
- يقدم صورة موحدة عن الشركة والمشاريع.

### Initiative

- يقدم Brief مفيدًا دون طلب يدوي.
- لا يرسل تنبيهات بلا قيمة.
- يعرف متى يحتاج تدخل أحمد.
- يرتب الأولويات حسب التأثير والاستعجال.

---

## 15. Proposed Roadmap

### Phase 0 — Current Fix Verification

- مراجعة تعديلات Claude.
- مراجعة Diff.
- تشغيل الاختبارات.
- اختبار الذاكرة والسياق.
- اعتماد أو رفض الإصلاح.

### Phase 1 — Memory Architecture

- تعريف أنواع الذاكرة.
- تعريف مصادر الحقيقة.
- Decision Ledger.
- Project Memory.
- Human Model.
- Retrieval rules.
- Correction and conflict rules.

### Phase 2 — Capabilities Registry + Phonebook

- تسجيل الأدوات الحالية.
- تعريف العقود.
- Verification لكل Capability.
- ربط الأدوات بالـ Agents.

### Phase 3 — Context Engine

- Relevant Memory Retrieval.
- Project context resolution.
- Dynamic recent history.
- Structured context package.

### Phase 4 — Executive Brain Upgrade

- Risk assessment.
- Real planning.
- Execution state.
- Verification.
- Learning decision contracts.

### Phase 5 — Initiative MVP

- Morning Brief.
- Missing reports.
- Upcoming deadlines.
- Pending decisions.
- Client follow-ups.

### Phase 6 — Bahr Designs Intelligence

- Site health score.
- Project delay prediction.
- Budget and cash alerts.
- Procurement risks.
- Client status.
- Portfolio-level dashboard.

---

## 16. Next Approved Working Order

لا نبدأ المرحلة التالية قبل إنهاء السابقة.

1. **مراجعة إصلاحات Claude الحالية.**
2. تثبيت النسخة السليمة وعمل Backup.
3. اعتماد مبدأ Memory Before Optimization.
4. بدء وثيقة Memory Architecture.
5. بناء Capabilities Registry + Phonebook.
6. تصميم Context Engine.
7. تطوير Initiative MVP.

---

## 17. Immediate Review Checklist for Claude

عند استلام رد Claude أو الملفات المعدلة، نراجع:

- [ ] هل أنشأ Backup؟
- [ ] هل أعاد History إلى `50 / 15`؟
- [ ] هل ألغى `memory_summary[-800:]`؟
- [ ] هل ألغى قطع `assistant_reply` عند 400 حرف؟
- [ ] هل أبقى `LearningDecision`؟
- [ ] هل عدّل فلتر الرسائل القصيرة؟
- [ ] هل منع استبعاد الاعتماد والتصحيح والرفض والاختيار؟
- [ ] هل عرض Diff لكل ملف؟
- [ ] هل توجد تغييرات غير مطلوبة؟
- [ ] هل عدّل Routing أو Architecture؟
- [ ] هل شغّل الاختبارات؟
- [ ] هل اختبر استمرارية محادثة طويلة؟
- [ ] هل اختبر ردودًا قصيرة مرتبطة بالسياق؟
- [ ] هل اختبر استرجاع قرار قديم؟

---

## 18. Current Status Summary

**Current workstream:** Token Optimization Repair Review  
**Blocked until:** Claude returns the modified files, Diff, and test results  
**Next document after approval:** ADAM Memory Architecture  
**Do not start yet:** Initiative implementation or new agents  
**Primary architectural principle:** Memory Before Optimization

---

## 19. North Star

> آدم لا يصبح خارقًا لأنه يكتب ردودًا مبهرة.  
> يصبح خارقًا عندما يتذكر ما يهم أحمد، ويرى ما قد يفوته، ويربط شغله كله، وينفذ، ويتحقق، ويخبره بما يحتاج معرفته في الوقت المناسب.
