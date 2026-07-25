# Checkpoint — 2026-07-24
مصدر هذا المستند: فحص مباشر لحالة الـ workspace (`git status`, `git diff`, قراءة ملفات فعلية، استعلام Firestore حي) — **مش من ذاكرة المحادثة**. أي حد (أو أي محادثة) يرجع لهذا المستند لازم يقدر يتحقق من كل سطر فيه بنفس الأوامر المذكورة.

---

## 0. لماذا هذا المستند موجود

حصل التباس بين محادثتين منفصلتين شغالتين على نفس الـ working directory (`adam-v1`):
- **هذه المحادثة**: بنت مشروع "ADAM Self-State & Observation System" على نطاق الأقساط فقط (مراحل 1-7 تحت).
- **محادثة أخرى منفصلة تمامًا** (~4 ساعات): بنت ملفات باسم "Truth/Meaning/Companionship" -- موجودة على القرص لكن **غير مربوطة بالنظام الحي إطلاقًا** (تفاصيل في قسم 3).

هذا المستند يثبّت الحقيقة الحالية القابلة للتحقق، بمعزل عن أي سياق محادثة مفقود.

---

## 1. حالة Git (وقت كتابة هذا المستند)

```
On branch main, up to date with origin/main.
```

### ملفات معدّلة (tracked, uncommitted) -- كلها تخص مراحل 1-7 فقط، اتفحصت diff بالكامل:
`.gitignore`, `config.py`, `handlers/voice_handler.py`, `main.py`, `morning_brief.py`, `services/claude_service.py`, `services/firebase_service.py`, `services/loan_service.py`
(+ `bahr_agent.log` -- ملف لوج، مش كود)

### ملفات جديدة تخص مراحل 1-7 (untracked):
`AUDIT_REPORT_STAGE0.md`, `EVENT_SCHEMA.md`, `LOAN_COMMAND_API_STAGE2.md`, `LOAN_CONFLICT_OBSERVER_STAGE3.md`, `CONFLICT_RESOLUTION_FLOW_STAGE4.md`, `SELF_STATE_ENGINE_STAGE5_DRAFT.md`, `SELF_STATE_ENGINE_STAGE5.md`, `VERIFIED_EXPRESSION_STAGE6_7_DRAFT.md`, `VERIFIED_EXPRESSION_STAGE6_7.md`, `services/event_store.py`, `services/loan_commands.py`, `services/loan_conflict_observer.py`, `services/self_state_engine.py`, `services/decision_engine.py`, `services/expression_vocabulary.py`, `services/verified_expression.py`, + ملفات `test_*.py` المرتبطة.

### ملفات جديدة **مش من هذه المحادثة** (من الجلسة التانية -- موجودة، غير مدمجة):
`TRUTH_LAYER_PHASE1.md`, `MEANING_LAYER_PHASE1.md`, `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md`, `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md`, `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md`, `services/truth_layer.py`, `services/meaning_layer.py`, `services/renderer.py`, `test_truth_layer.py`, `test_meaning_layer.py`, `test_renderer.py`, `test_claim_validator.py`

---

## 2. مراحل 1-7 (الأقساط) -- الحالة الفعلية المؤكدة

كل التغييرات في الملفات المعدّلة اتفحصت بـ `git diff` سطر بسطر (مش بالذاكرة) وطابقت بالكامل المتوقع:

| الملف | التأكيد |
|---|---|
| `services/event_store.py` | Event Store كامل (`record_event`, `record_event_with_write`, `get_events_for_entity`, `get_events_by_type_and_attribute`) |
| `services/loan_commands.py` | `loan_record_installment` (بتوقف عند تعارض)، `loan_update_installment`، `loan_resolve_conflict` -- كلهم بيسجلوا حدث `conflict_status` |
| `services/loan_conflict_observer.py` | تصنيف new/duplicate/update/conflict |
| `services/self_state_engine.py` | 3 أبعاد: `unresolved_conflict` (high=3)، `pending_obligation_load` (concern=2)، `tracking_stability` (frequent_corrections=5) |
| `services/decision_engine.py` | Active/Passive بمنطق transition-only |
| `services/expression_vocabulary.py` + `services/verified_expression.py` | القاموس المقفول + Gate (Information Containment, Verbatim Match Validator, Evidence Trace) |
| `services/claude_service.py` | **مؤكد بـ diff كامل**: `loan_mark_paid` القديمة محذوفة، 3 أدوات جديدة + `request_verified_expression` (بدون `mode`) موجودين، القيود في الـ system prompt موجودة بالحرف |
| `main.py` | **مؤكد بـ diff كامل**: `verify_and_finalize` مربوطة في `handle_message` + **9 فروع** `handle_callback` + `weekly_report_job`. `self_state_active_check_job` مسجّلة في الـ scheduler (كل ساعة) |
| `morning_brief.py`, `handlers/voice_handler.py` | **مؤكد بـ diff**: `verify_and_finalize` مربوطة في الاتنين |
| `services/loan_service.py`, `services/firebase_service.py` | **مؤكد بـ diff**: الكود الميت القديم (`mark_installment_paid`, `set_paid`, `save_loan_paid_status`) محذوف فعليًا |

**سويپ شامل لكل نقاط استخدام `ask_claude_agentic`** (الدالة الوحيدة اللي فيها `tools=TOOLS`) اتعمل ويؤكد: **11 نقطة إرسال** كلها مربوطة بـ `verify_and_finalize` (`handle_message`, 9× `handle_callback`, `weekly_report_job`, `send_morning_brief`, `voice_handler`). باقي الدوال (`ask_claude`, `analyze_with_vision`, `extract_*`) لا تملك وصول للأدوات إطلاقًا -- لا حاجة لربطها.

**فحص نحوي واستيراد فعلي (وقت كتابة هذا المستند):**
```
14 ملف (event_store, loan_commands, loan_conflict_observer, self_state_engine,
decision_engine, expression_vocabulary, verified_expression, claude_service,
loan_service, firebase_service, main, morning_brief, voice_handler, config)
→ ALL SYNTAX OK
import main → FULL IMPORT OK (لا أخطاء)
```

---

## 3. ملفات Truth/Meaning/Companionship -- موجودة، لكن غير مدمجة

فحص مباشر (`grep` على الاستيرادات) أثبت:
- `services/truth_layer.py`, `services/meaning_layer.py`, `services/renderer.py` **لا يستوردون أي شيء** من ملفات مراحل 1-7 (event_store, loan_commands, self_state_engine, verified_expression, decision_engine, إلخ) -- استيراداتهم فقط: `uuid`, `dataclasses`, `datetime`, `typing`, `re`, `utils.time_utils`.
- ولا أي ملف من مراحل 1-7 يستورد منهم.
- `services/claude_service.py` و`main.py` (اللي بيحددوا الأدوات وربط الإرسال) **لا يذكرون** `truth_layer`/`meaning_layer`/`renderer` إطلاقًا.

**الخلاصة:** الملفات دي موجودة على القرص كنتاج محادثة منفصلة، لكنها **غير مربوطة بأي نقطة تشغيل حية** (مش في TOOLS، مش في أي dispatch، مش في أي scheduler job). لا تأثير لها على مراحل 1-7، ولا العكس. **لا يعتبر أي منها "منفّذ" أو "معتمد"** حتى يقدَّم لهذه المحادثة تصميم صريح منفصل يُراجَع من الصفر.

---

## 4. حالة Firestore الحية (فحص مباشر وقت كتابة هذا المستند)

```
adam_events            → 0 وثيقة
adam_self_state        → 0 وثيقة
adam_state_snapshots   → 0 وثيقة
adam_expressions       → 0 وثيقة

loans/paid_status → {
  "paid": {"ca_71": false, "ca_70": false, "ca_69": false},
  "paid.ca_71": true   ← أثر قديم معروف من Stage 2 (باگ nested-merge قبل الإصلاح),
                          موثّق سابقًا، غير مقروء من أي كود، بانتظار تنظيف يدوي
                          اختياري من Firebase console وقتما تشاء.
}

Self-State الحية الآن:
  unresolved_conflict      → none (0)
  pending_obligation_load  → concern (7 قسط متأخر عن ميعاده -- بيانات حقيقية،
                              متسقة مع الـ Audit الأول: لا شيء اتسجل كمدفوع بعد)
  tracking_stability       → none (0)
```

---

## 5. ما لم يحدث في هذا التحقق (بالتصريح)

- **لم تُنفَّذ أي مرحلة جديدة.** هذا فحص وتوثيق فقط، بناءً على طلب صريح.
- لم يُلمَس أي ملف من ملفات Truth/Meaning/Companionship.
- لم يُفترض أي محتوى لتلك الملفات أو لأي "خطة migration" -- لم تتم قراءتها بالتفصيل، فقط فحص استيراداتها للتأكد من الاستقلالية.

---

## 6. نقطة الاستئناف الآمنة

مراحل 1-7 (الأقساط): **مؤكدة، ثابتة، مستقلة تمامًا عن أي عمل آخر.** جاهزة كأساس متين لأي خطوة تالية.

في انتظار متطلبات التصميم الجديد الصريح (وليس كاستمرارية مفترضة) لأي عمل متعلق بـ Truth/Meaning/Companionship.
