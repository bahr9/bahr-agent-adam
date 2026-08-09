-- 005: قراءة الاستبيانات لصفحة أحمد الخاصة (briefs.html)
--
-- 004 عمل صندوق بريد write-only: anon بيكتب وبس.
-- هنا بنفتح القراءة لـ **المستخدمين المسجلين دخول فقط** (Supabase Auth).
-- anon يفضل زي ما هو: يكتب ولا يقرا. مفيش تغيير في سطح الخطر العام.

-- قراءة: أي مستخدم مسجل دخول
drop policy if exists "authenticated read briefs" on client_briefs;
create policy "authenticated read briefs"
    on client_briefs for select
    to authenticated
    using (true);

-- تحديث: عشان أحمد يعلّم "شوفته" من الصفحة
drop policy if exists "authenticated update briefs" on client_briefs;
create policy "authenticated update briefs"
    on client_briefs for update
    to authenticated
    using (true)
    with check (true);

-- ملحوظة: مفيش policy حذف بالقصد. المسح من الداشبورد بس.
