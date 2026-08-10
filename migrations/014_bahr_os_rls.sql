-- ============================================================
-- 014 — حماية جداول BAHR OS
-- ============================================================
-- التاريخ: 2026-08-10
--
-- ميجريشن 003 بيعمل تسعتاشر جدول فيهم فواتير ومشتريات وأسعار،
-- **ومفيهوش سطر RLS واحد**. من غير الملف ده، تشغيل 003 معناه إن
-- الجداول دي تتقرا وتتكتب بالمفتاح العام -- والمفتاح العام مكتوب
-- في صفحات منشورة على النت.
--
-- القاعدة هنا واحدة وبسيطة: **الداخل بحسابه بس**.
-- مفيش وصول للمجهول (anon) خالص -- لا قراءة ولا كتابة.
--
-- ده مختلف عن `client_briefs` بالقصد: هناك المجهول بيكتب البريف
-- (صندوق بريد: INSERT بس من غير SELECT) لأن العميل بيملا استمارة
-- من غير حساب. هنا مفيش سبب لحد من برّه يلمس أي حاجة.
--
-- شغّل 003 الأول، وبعده الملف ده على طول.
-- ============================================================

begin;

do $$
declare
    t text;
    tables text[] := array[
        'projects',
        'project_phase_estimates',
        'project_phase_items',
        'project_quantity',
        'project_quantity_items',
        'project_quantity_item_images',
        'invoices',
        'invoice_items',
        'invoice_item_purchases',
        'invoice_signatures',
        'site_reports',
        'site_report_handover',
        'site_report_images',
        'purchases',
        'purchase_items',
        'purchase_receipt_images',
        'bahr_sites',
        'user_projects',
        'notifications'
    ];
begin
    foreach t in array tables loop
        -- الجدول اللي مش موجود بيتخطى بدل ما يوقف الميجريشن كله:
        -- 003 ممكن يكون اتشغل ناقص، والحماية على اللي موجود أهم من
        -- إنها تفشل كلها عشان جدول واحد.
        if not exists (
            select 1 from pg_tables
            where schemaname = 'public' and tablename = t
        ) then
            raise notice 'تخطّي %: الجدول مش موجود', t;
            continue;
        end if;

        execute format('alter table public.%I enable row level security', t);

        -- سياسة واحدة لكل الأفعال: الداخل بحسابه يعمل كل حاجة.
        -- (منظومة مستخدم واحد -- التقسيم لأدوار بيتعمل لما يبقى فيه أدوار)
        execute format('drop policy if exists %I on public.%I',
                       t || '_authenticated_all', t);
        execute format(
            'create policy %I on public.%I for all to authenticated '
            'using (true) with check (true)',
            t || '_authenticated_all', t);
    end loop;
end $$;

commit;


-- ============================================================
-- التأكد بعد التشغيل
-- ============================================================
-- لازم ترجّع 19 صف، وكلهم rowsecurity = true وpolicies = 1:
--
--   select c.relname,
--          c.relrowsecurity as rls,
--          count(p.polname)  as policies
--     from pg_class c
--     join pg_namespace n on n.oid = c.relnamespace
--     left join pg_policy p on p.polrelid = c.oid
--    where n.nspname = 'public'
--      and c.relname in (
--          'projects','project_phase_estimates','project_phase_items',
--          'project_quantity','project_quantity_items',
--          'project_quantity_item_images','invoices','invoice_items',
--          'invoice_item_purchases','invoice_signatures','site_reports',
--          'site_report_handover','site_report_images','purchases',
--          'purchase_items','purchase_receipt_images','bahr_sites',
--          'user_projects','notifications')
--    group by 1, 2
--    order by 1;
--
-- أي صف بـ rls = false معناه جدول مكشوف. متكملش قبل ما يتظبط.
-- ============================================================
