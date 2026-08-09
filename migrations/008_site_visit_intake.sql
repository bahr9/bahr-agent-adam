-- 008: استلام المعاينة -- التسجيل والسكيتش والنوت
--
-- تصحيح تصميمي (2026-08-09): الصفحة **مش بتسجل**، بتستلم.
-- تسجيل اجتماع 40 دقيقة من تبويب متصفح بيموت مع أول تليفون أو قفل شاشة،
-- ومسجل الموبايل العادي أضمن منه بمراحل وأحمد بيستعمله أصلًا. فالرفع
-- بيحصل بعد الزيارة، مش خلالها.
--
-- الملفات في bucket خاص `site-visits` (اتعمل بالـ API)، والمسار
-- site-visits/{session_id}/... يعني الربط بالبريف من غير جدول جديد.
-- النوت عمود على client_briefs زي project_id -- نفس النمط، صفر جداول جديدة.

alter table client_briefs add column if not exists site_note text;

-- صلاحيات التخزين: أحمد المسجل دخول بس. مفيش anon خالص --
-- ده مش صندوق بريد عام زي الاستبيان، ده شغل داخلي.
drop policy if exists "authenticated upload site visits" on storage.objects;
create policy "authenticated upload site visits"
    on storage.objects for insert to authenticated
    with check (bucket_id = 'site-visits');

drop policy if exists "authenticated read site visits" on storage.objects;
create policy "authenticated read site visits"
    on storage.objects for select to authenticated
    using (bucket_id = 'site-visits');

drop policy if exists "authenticated delete site visits" on storage.objects;
create policy "authenticated delete site visits"
    on storage.objects for delete to authenticated
    using (bucket_id = 'site-visits');
