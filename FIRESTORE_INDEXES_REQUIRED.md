# الـ Composite Indexes المطلوبة في Firestore

الملف ده فيه كل الـ indexes اللي الكود محتاجها. اضغط على اللينك، Firebase
هيفتحلك صفحة الإنشاء والحقول متملية جاهزة — اضغط "Create Index" وبس.
الإنشاء بياخد دقايق قليلة على البيانات الحالية.

---

## 1. `memory_notes` — `user_id` + `createdAt`

**الحالة:** ناقص من 21 يوليو 2026. البحث في الملاحظات وجلبها **بيفشلوا** حاليًا
(`❌ خطأ في البحث: 400` متكرر في اللوج).

**بيأثر على:** `search_memory_notes`, `list_memory_notes`

https://console.firebase.google.com/v1/r/project/bahr-designs-office/firestore/indexes?create_composite=Clhwcm9qZWN0cy9iYWhyLWRlc2lnbnMtb2ZmaWNlL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9tZW1vcnlfbm90ZXMvaW5kZXhlcy9fEAEaCwoHdXNlcl9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC

---

## 2. `adam_events` — `entity_key` + `occurred_at`

**الحالة:** ناقص. الكود شغال دلوقتي بـ fallback غير مرتّب (بيحذّر في اللوج)،
يعني "آخر حدث" لسه ممكن يطلع مش آخر حدث فعلاً.

**بيأثر على:** تصنيف تعارض الأقساط، تقرير دورة حياة الأدوات، عدّادات التشخيص

https://console.firebase.google.com/v1/r/project/bahr-designs-office/firestore/indexes?create_composite=Cldwcm9qZWN0cy9iYWhyLWRlc2lnbnMtb2ZmaWNlL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9hZGFtX2V2ZW50cy9pbmRleGVzL18QARoOCgplbnRpdHlfa2V5EAEaDwoLb2NjdXJyZWRfYXQQAhoMCghfX25hbWVfXxAC

---

## 3. `adam_events` — `type_attribute_key` + `occurred_at`

**الحالة:** ناقص. نفس الـ fallback.

**بيأثر على:** `compute_unresolved_conflict` في Self-State (ممكن يطلّع تحذيرات
تعارض وهمية لأن حدث الحل نفسه مش داخل العينة)

https://console.firebase.google.com/v1/r/project/bahr-designs-office/firestore/indexes?create_composite=Cldwcm9qZWN0cy9iYWhyLWRlc2lnbnMtb2ZmaWNlL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9hZGFtX2V2ZW50cy9pbmRleGVzL18QARoWChJ0eXBlX2F0dHJpYnV0ZV9rZXkQARoPCgtvY2N1cnJlZF9hdBACGgwKCF9fbmFtZV9fEAI

---

## إزاي تتأكد إنها اشتغلت

بعد ما الـ indexes تخلص، شغّل:

```bash
python test_tool_lifecycle_diagnostics.py
```

الاختبار ده حاليًا **بيفشل** عند
`assert status2["payload_included"] is False` — لأن الاستعلام غير المرتّب
بيرجع عينة عشوائية من آلاف الأحداث، فالـ snapshot اللي الاختبار لسه كاتبه
مش بيكون هو الأخير. أول ما الـ index رقم 2 يشتغل، الاختبار المفروض يعدّي.

وكمان تحذير `⚠️ استعلام مرتّب فشل` المفروض يختفي من اللوج خالص.
