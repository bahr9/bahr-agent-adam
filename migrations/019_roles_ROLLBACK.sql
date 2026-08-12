-- ============================================================
-- رجوع عن ٠١٩ — لو الأدوار قفلت على أحمد
-- ============================================================
-- بيرجّع سلوك ٠١٤: أي داخل بحسابه يعمل كل حاجة.
--
-- ⚠️ ده **بيفتح كل حاجة تاني**. استعمله لو BAHR OS وقف بسبب ٠١٩،
--    وبعدين نشوف الغلط بالراحة. وماتنشرش تطبيق المشرفين وإنت راجع
--    للحالة دي.
--
-- علامة إنك محتاجه: تفتح BAHR OS وتلاقي «مقدرتش أقرا» في كل تاب،
-- أو قايمة المشاريع فاضية وإنت مسجّل دخول.

begin;

do $$
declare
    t text;
    p record;
    tables text[] := array[
        'projects', 'project_phase_estimates', 'project_phase_items',
        'project_quantity', 'project_quantity_items', 'project_quantity_item_images',
        'invoices', 'invoice_items', 'invoice_item_purchases', 'invoice_signatures',
        'site_reports', 'site_report_handover', 'site_report_images',
        'purchases', 'purchase_items', 'purchase_receipt_images',
        'bahr_sites', 'user_projects', 'notifications', 'app_roles'
    ];
begin
    foreach t in array tables loop
        if not exists (select 1 from pg_tables
                       where schemaname = 'public' and tablename = t) then
            continue;
        end if;

        -- شيل كل سياسات ٠١٩ على الجدول ده
        for p in
            select polname from pg_policy
            where polrelid = format('public.%I', t)::regclass
        loop
            execute format('drop policy if exists %I on public.%I', p.polname, t);
        end loop;

        -- ورجّع سياسة ٠١٤ المفتوحة
        execute format(
            'create policy %I on public.%I for all to authenticated '
            'using (true) with check (true)',
            t || '_authenticated_all', t);
    end loop;
end $$;

commit;

-- ============================================================
--   select polname from pg_policy where polname like '%_authenticated_all';
--   -- لازم ترجّع ٢٠ صف (١٩ جدول + app_roles)
-- ============================================================
