-- ============================================================
-- 019 — أدوار: صاحب المكتب ومشرف الموقع
-- ============================================================
-- التاريخ: 2026-08-11
--
-- ميجريشن ٠١٤ كتب بالحرف:
--
--   «سياسة واحدة لكل الأفعال: الداخل بحسابه يعمل كل حاجة.
--    (منظومة مستخدم واحد -- التقسيم لأدوار بيتعمل لما يبقى فيه أدوار)»
--
-- والنهاردة بقى فيه أدوار: تطبيق المشرفين (`site.html`) بيتنشر لتلات
-- مشرفين من برّه المكتب.
--
-- من غير الملف ده، أي مشرف يسجّل دخول بيبقى له **قراءة وكتابة على كل
-- حاجة**: المقايسات والأسعار والفواتير ومشاريع تانية. والفحص اللي في
-- `site.html` (`allowedSupervisors.includes(email)`) في المتصفح --
-- بيحدد الشاشة بتوري إيه، مش بيمنع طلب.
--
-- ## الدورين
--
--   owner       -- أحمد. كل حاجة.
--   supervisor  -- مشرف موقع. **مشاريعه بس**، ومن غير أي سعر.
--
-- ## اللي المشرف مايشوفهوش أبدًا
--
-- المقايسات والحصر والفواتير وقاعدة الأسعار. دي شغل المكتب، ومفيش
-- سبب تظهر لمقاول في الموقع.
--
-- ⚠️ الملف ده **بيبدّل** سياسات ٠١٤. لو اتشغّل والجدول مالوش سياسة
--    جديدة، بيبقى مقفول تمامًا (RLS شغّال + صفر سياسات = رفض).
--    عشان كده كل جداول ٠١٤ متغطّاة هنا.

begin;

-- ============================================================
-- 1. مين مين
-- ============================================================
-- جدول صغير بالإيميل. الإيميل بييجي من التوكن (`auth.jwt()`)، فمفيش
-- حاجة الفرونت يقدر يزوّرها.
create table if not exists public.app_roles (
    email      text primary key,
    role       text not null,
    note       text,
    created_at timestamptz not null default now(),
    constraint app_roles_role_valid check (role in ('owner', 'supervisor'))
);

comment on table public.app_roles is
    'مين له إيه. الإيميل بيتقارن بـauth.jwt()->>email -- مش بحاجة '
    'الفرونت بيبعتها. الجدول ده نفسه للمالك بس.';

alter table public.app_roles enable row level security;

-- 🔴 الصفوف دي لازم تفضل. من غيرها مفيش مالك، ويبقى كل حاجة مقفولة.
--
-- **الاتنين** بالقصد: أحمد بيدخل BAHR OS بـarch.ahmed25 (ده الحساب
-- الوحيد في Firebase Auth)، وجلسة Supabase كانت بتيجي من bahrdesigns9
-- المحفوظة في المتصفح. لو المالك واحد بس، أي طريق من الاتنين ممكن
-- يقفل عليه.
--
-- ⚠️ وarch.ahmed25 موجود في `allowed_supervisors` بتاع روك إيدن.
--    كونه مالك هنا **بيغلب** -- سياسة المالك بتدي كل حاجة. لو المفروض
--    يبقى مشرف بجد، يتشال من هنا ويتشال دوره.
insert into public.app_roles (email, role, note) values
    ('bahrdesigns9@gmail.com', 'owner', 'أحمد — حساب Supabase'),
    ('arch.ahmed25@gmail.com', 'owner', 'أحمد — حساب الدخول في BAHR OS')
on conflict (email) do update set role = 'owner';


create or replace function public.jwt_email()
returns text
language sql
stable
as $$
    select nullif(auth.jwt() ->> 'email', '')
$$;

create or replace function public.is_owner()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1 from public.app_roles
        where email = public.jwt_email() and role = 'owner'
    )
$$;

-- المشرف على المشروع ده؟ `allowed_supervisors` عمود إيميلات على
-- المشروع نفسه -- نفس اللي `site.html` بيفحصه، بس هنا في القاعدة.
create or replace function public.supervises(p_project text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1 from public.projects
        where id = p_project
          and public.jwt_email() = any (coalesce(allowed_supervisors, '{}'))
    )
$$;

revoke all on function public.is_owner() from public;
revoke all on function public.supervises(text) from public;
grant execute on function public.jwt_email()      to authenticated;
grant execute on function public.is_owner()       to authenticated;
grant execute on function public.supervises(text) to authenticated;

-- المالك بس هو اللي يقرا/يعدّل الأدوار
drop policy if exists app_roles_owner on public.app_roles;
create policy app_roles_owner on public.app_roles
    for all to authenticated using (public.is_owner()) with check (public.is_owner());


-- ============================================================
-- 2. شيل سياسات ٠١٤ المفتوحة
-- ============================================================
do $$
declare
    t text;
    tables text[] := array[
        'projects', 'project_phase_estimates', 'project_phase_items',
        'project_quantity', 'project_quantity_items', 'project_quantity_item_images',
        'invoices', 'invoice_items', 'invoice_item_purchases', 'invoice_signatures',
        'site_reports', 'site_report_handover', 'site_report_images',
        'purchases', 'purchase_items', 'purchase_receipt_images',
        'bahr_sites', 'user_projects', 'notifications'
    ];
begin
    foreach t in array tables loop
        if exists (select 1 from pg_tables
                   where schemaname = 'public' and tablename = t) then
            execute format('drop policy if exists %I on public.%I',
                           t || '_authenticated_all', t);
        end if;
    end loop;
end $$;


-- ============================================================
-- 3. المالك بس — شغل المكتب
-- ============================================================
-- المقايسات والحصر والفواتير والأسعار. المشرف مايشوفهاش.
do $$
declare
    t text;
    tables text[] := array[
        'project_phase_estimates', 'project_phase_items',
        'project_quantity', 'project_quantity_items', 'project_quantity_item_images',
        'invoices', 'invoice_items', 'invoice_item_purchases', 'invoice_signatures',
        'bahr_sites', 'user_projects'
    ];
begin
    foreach t in array tables loop
        if exists (select 1 from pg_tables
                   where schemaname = 'public' and tablename = t) then
            execute format('drop policy if exists %I on public.%I', t || '_owner', t);
            execute format(
                'create policy %I on public.%I for all to authenticated '
                'using (public.is_owner()) with check (public.is_owner())',
                t || '_owner', t);
        end if;
    end loop;
end $$;


-- ============================================================
-- 4. المشاريع — المالك كل حاجة، المشرف يقرا مشاريعه بس
-- ============================================================
drop policy if exists projects_owner on public.projects;
create policy projects_owner on public.projects
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

-- قراءة بس. المشرف مايغيّرش اسم مشروع ولا مساحته ولا -- الأهم --
-- قايمة المشرفين نفسها.
drop policy if exists projects_supervisor_read on public.projects;
create policy projects_supervisor_read on public.projects
    for select to authenticated
    using (public.jwt_email() = any (coalesce(allowed_supervisors, '{}')));


-- ============================================================
-- 5. تقارير الموقع — ده شغل المشرف
-- ============================================================
drop policy if exists site_reports_owner on public.site_reports;
create policy site_reports_owner on public.site_reports
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

drop policy if exists site_reports_supervisor on public.site_reports;
create policy site_reports_supervisor on public.site_reports
    for all to authenticated
    using (public.supervises(project_id))
    with check (public.supervises(project_id));

-- الجداول التابعة بتمشي على تقريرها
drop policy if exists site_report_handover_owner on public.site_report_handover;
create policy site_report_handover_owner on public.site_report_handover
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

drop policy if exists site_report_handover_supervisor on public.site_report_handover;
create policy site_report_handover_supervisor on public.site_report_handover
    for all to authenticated
    using (exists (select 1 from public.site_reports r
                   where r.id = site_report_id and public.supervises(r.project_id)))
    with check (exists (select 1 from public.site_reports r
                        where r.id = site_report_id and public.supervises(r.project_id)));

drop policy if exists site_report_images_owner on public.site_report_images;
create policy site_report_images_owner on public.site_report_images
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

drop policy if exists site_report_images_supervisor on public.site_report_images;
create policy site_report_images_supervisor on public.site_report_images
    for all to authenticated
    using (exists (select 1 from public.site_reports r
                   where r.id = site_report_id and public.supervises(r.project_id)))
    with check (exists (select 1 from public.site_reports r
                        where r.id = site_report_id and public.supervises(r.project_id)));


-- ============================================================
-- 6. المشتريات — المشرف يطلب ويرفع فواتير، والاعتماد للمالك
-- ============================================================
drop policy if exists purchases_owner on public.purchases;
create policy purchases_owner on public.purchases
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

drop policy if exists purchases_supervisor_read on public.purchases;
create policy purchases_supervisor_read on public.purchases
    for select to authenticated using (public.supervises(project_id));

drop policy if exists purchases_supervisor_insert on public.purchases;
create policy purchases_supervisor_insert on public.purchases
    for insert to authenticated with check (public.supervises(project_id));

-- التعديل مسموح، **والمسح لأ**. أمر شراء اتنفّذ ومسحته = بند في
-- المستخلص مالوش أصل (قرار مستني في الخطة -- لحد ما يتحسم، المسح
-- للمالك بس).
drop policy if exists purchases_supervisor_update on public.purchases;
create policy purchases_supervisor_update on public.purchases
    for update to authenticated
    using (public.supervises(project_id))
    with check (public.supervises(project_id));

drop policy if exists purchase_items_owner on public.purchase_items;
create policy purchase_items_owner on public.purchase_items
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

drop policy if exists purchase_items_supervisor on public.purchase_items;
create policy purchase_items_supervisor on public.purchase_items
    for all to authenticated
    using (exists (select 1 from public.purchases p
                   where p.id = purchase_id and public.supervises(p.project_id)))
    with check (exists (select 1 from public.purchases p
                        where p.id = purchase_id and public.supervises(p.project_id)));

drop policy if exists purchase_receipt_images_owner on public.purchase_receipt_images;
create policy purchase_receipt_images_owner on public.purchase_receipt_images
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

drop policy if exists purchase_receipt_images_supervisor on public.purchase_receipt_images;
create policy purchase_receipt_images_supervisor on public.purchase_receipt_images
    for all to authenticated
    using (exists (select 1 from public.purchases p
                   where p.id = purchase_id and public.supervises(p.project_id)))
    with check (exists (select 1 from public.purchases p
                        where p.id = purchase_id and public.supervises(p.project_id)));


-- ============================================================
-- 7. الإشعارات — المشرف يبعت، المالك يقرا
-- ============================================================
drop policy if exists notifications_owner on public.notifications;
create policy notifications_owner on public.notifications
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

-- إدخال بس: الإشعار بيتبعت للمكتب، والمشرف مايقراش صندوق غيره.
drop policy if exists notifications_supervisor_insert on public.notifications;
create policy notifications_supervisor_insert on public.notifications
    for insert to authenticated
    with check (project_id is null or public.supervises(project_id));

commit;


-- ============================================================
-- التأكد بعد التشغيل
-- ============================================================
-- ١. مفيش جدول اتساب من غير سياسة (RLS شغّال + صفر سياسات = مقفول):
--
--   select c.relname, count(p.polname) as policies
--     from pg_class c
--     join pg_namespace n on n.oid = c.relnamespace
--     left join pg_policy p on p.polrelid = c.oid
--    where n.nspname = 'public' and c.relrowsecurity
--    group by 1 having count(p.polname) = 0;
--
--   لازم ترجّع **صفر صفوف**.
--
-- ٢. مفيش سياسة قديمة مفتوحة فاضلة:
--
--   select polname from pg_policy where polname like '%_authenticated_all';
--   -- لازم صفر.
--
-- ٣. المالك موجود:
--
--   select * from public.app_roles where role = 'owner';
--   -- لازم صف واحد على الأقل، وإلا كل حاجة مقفولة.
--
-- ⚠️ والفحص الحقيقي مش ده: لازم تتجرّب بجلسة **مشرف** حقيقية وتتأكد
--    إن `project_phase_items` بترجع صفر صفوف. الفحص من مفتاح الخدمة
--    بيتخطى RLS وبيقول «شغّال» وهو مش بيفحص حاجة.
-- ============================================================
