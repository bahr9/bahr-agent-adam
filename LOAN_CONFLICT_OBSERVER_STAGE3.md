# Loan Conflict Observer — Stage 3
تاريخ: 2026-07-24
الحالة: **منفّذ ومتحقق منه فعليًا** ضد Firestore الحقيقي — كل التصنيفات الأربعة.
المرجع السابق: [EVENT_SCHEMA.md](EVENT_SCHEMA.md), [LOAN_COMMAND_API_STAGE2.md](LOAN_COMMAND_API_STAGE2.md)

---

## 1. اللي اتعمل

[services/loan_conflict_observer.py](services/loan_conflict_observer.py) — بيراقب أحداث الأقساط في الـ Event Store ويصنّف آخر حدث لكل entity بالنسبة للي قبله:

| التصنيف | الشرط |
|---|---|
| **new** | أول حدث خالص لـ entity+attribute ده -- مفيش تاريخ يتقارن بيه. |
| **duplicate** | نفس القيمة اللي كانت متسجلة قبله -- مفيش تغيير حقيقي في الحالة. |
| **update** | القيمة اتغيّرت عبر قناة تصحيح صريحة موثّقة بسبب (`loan_update_installment` أو `loan_resolve_conflict`). |
| **conflict** | القيمة اتغيّرت عبر `loan_record_installment` (قناة "أول تسجيل") رغم وجود قيمة سابقة مختلفة متسجلة -- ادّعاءين متضاربين من غير توثيق تصحيح. |

التصنيف مبني **حصريًا** على الأحداث المسجلة فعليًا في `adam_events` -- مفيش تخمين، ومفيش حالة داخلية موازية بتتخزن في مكان تاني.

---

## 2. Normalization -- ليه مفيش خطوة تطبيع منفصلة هنا

التصميم الأصلي طلب "Normalize (identity_key = normalized_program + billing_period)". فعليًا، التطبيع ده **بيحصل فعلاً** لكن في مكان تاني: `loan_commands._resolve_installment()` (Stage 2) بياخد اسم مرن (فاليو / Valu / فاليو) ويحوّله لـ `program['id']` الثابت (زي `"ca"`) + رقم الشهر (`index`) وقت الكتابة، فالـ `entity_id` (زي `"ca_71"`) المتسجل في الحدث نفسه **already normalized** من الأساس. الـ Observer هنا مبيحتاجش يعيد نفس الشغل وقت القراءة -- بيقرأ identity_key ثابت وموحّد أصلاً.

---

## 3. نطاق Stage 3 (مهم -- حدود واضحة)

- الـ Observer **بيصنّف ويسجّل لوج بس**. **مبيوقفش** أي كتابة، ومبياخدش تأكيد من حد.
- اتربط تلقائيًا في `loan_commands._commit()`: بعد كل كتابة ناجحة، بينادى `classify_installment()`، ولو التصنيف طلع `conflict`، بيتضاف سطر ملحوظة (⚠️) في الرسالة الراجعة لآدم/أحمد -- **معلومة بس، مش حاجز**.
- "الوقف + التأكيد اليدوي الإجباري من أحمد" هو **صلب Stage 4** (Conflict Resolution Flow) اللي لسه مش متبنية. Stage 3 بس بيوفر الإشارة اللي Stage 4 هيبني عليها قراره.

---

## 4. التحقق الفعلي (Verification)

اتعمل بالكامل ضد Firestore الحقيقي، على نفس القسط الآمن من Stage 2 (Credit Agricole، 01/06/2032):

1. ✅ `classify_installment` بيرجع `None` لما مفيش أي تاريخ خالص.
2. ✅ أول تسجيل (`loan_record_installment`, paid=True) → `new`.
3. ✅ تسجيل نفس القيمة تاني → `duplicate`.
4. ✅ تسجيل قيمة مختلفة عبر `loan_record_installment` تاني (مش `update`) → `conflict`، والرسالة الراجعة فعليًا فيها ⚠️ الملحوظة.
5. ✅ تصحيح صريح بسبب (`loan_update_installment`) → `update`.
6. ✅ حل تعارض يدوي (`loan_resolve_conflict`) → `update` (قناة صريحة موثّقة برضه)، ورجّع القيمة لأصلها بالظبط.
7. ✅ القيمة النهائية للقسط رجعت لنفس حالتها الأصلية (`False`).
8. 🧹 كل الـ 5 أحداث الاختبار اتمسحت من `adam_events` بعد التأكيد.

---

## 5. Definition of Done — مرحلة 3 (مقترح للاعتماد)

- [x] `loan_conflict_observer.py` منفّذ، بيصنّف الأربع حالات (new/duplicate/update/conflict) حصريًا من الـ Event Store.
- [x] متربط تلقائيًا بعد كل كتابة في `loan_commands._commit()` -- بدون حظر أي عملية.
- [x] `identity_key` مؤكد إنه already normalized من Stage 2 -- مفيش تطبيع مكرر.
- [x] تحقق فعلي (مش نظري) للأربع تصنيفات كلهم ضد بيانات حقيقية، مع رجوع القيمة لأصلها والتنظيف الكامل بعد التحقق.
- [ ] **قرار أحمد:** اعتماد المرحلة كـ "خلصت" والانتقال لمرحلة 4 (Conflict Resolution Flow -- الوقف + التأكيد اليدوي الفعلي).
